# SPDX-License-Identifier: Apache-2.0
"""Job queue: one worker thread processes one post at a time.

Transcription is CPU-heavy, so jobs run strictly one after another. Every job
lives in DATA_DIR/jobs/<id>/ and is deleted after SHAREWERK_RETENTION_HOURS.
State is mirrored to job.json so a container restart does not lose results.
"""

from __future__ import annotations

import json
import logging
import queue
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from .config import Settings
from .fetch import FetchError, FetchResult, fetch
from .process import build_pack, mime_for, originals, share_batches
from .urls import Target

log = logging.getLogger(__name__)

TERMINAL = {"done", "error"}
STORAGE_FAILED = "storage_failed"


class StorageError(OSError):
    """job.json could not be written (full disk, read-only volume ...)."""


@dataclass
class Job:
    id: str
    url: str
    platform: str
    kind: str
    key: str
    status: str = "queued"  # queued | running | done | error
    stage: str = "queued"  # queued | downloading | processing | transcribing | done
    error_code: str = ""
    error_detail: str = ""
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    result: dict | None = None

    def public(self) -> dict:
        data = asdict(self)
        return data


Runner = Callable[[Job, Path, Settings, Callable[[str], None]], dict]


def default_runner(job: Job, workdir: Path, settings: Settings, set_stage: Callable[[str], None]) -> dict:
    target = Target(job.url, job.platform, job.kind, job.key)
    set_stage("downloading")
    fetched = fetch(target, workdir, settings)
    pack = build_pack(fetched, workdir, settings, on_stage=set_stage)
    return manifest(job, fetched, pack, workdir)


def manifest(job: Job, fetched: FetchResult, pack, workdir: Path) -> dict:
    out = workdir / "out"
    base = f"{job.platform}-{job.key}"
    (out / "post.txt").write_text(pack.text_full, encoding="utf-8")
    files: dict[str, dict] = {
        "post.txt": {"path": "out/post.txt", "name": f"{base}.txt", "type": "text/plain"},
    }
    if pack.text_compact:
        (out / "post-compact.txt").write_text(pack.text_compact, encoding="utf-8")
        files["post-compact.txt"] = {"path": "out/post-compact.txt", "name": f"{base}.txt", "type": "text/plain"}

    for i, v in enumerate(pack.visuals, start=1):
        files[v.file] = {
            "path": f"out/{v.file}", "name": f"{base}-{i:02d}.jpg", "type": "image/jpeg", "label": v.label(),
            "number": i, "kind": v.kind, "item": v.item, "time": v.time,
        }
    for name, numbers in pack.sheets:
        files[name] = {
            "path": f"out/{name}", "name": f"{base}-{name}", "type": "image/jpeg",
            "label": f"pictures {numbers[0]}-{numbers[-1]}",
        }

    orig_names: list[str] = []
    for item in originals(fetched.items):
        served = f"original-{item.index:02d}{item.path.suffix.lower()}"
        files[served] = {
            "path": str(item.path.resolve().relative_to(workdir.resolve())),
            "name": f"{base}-{item.index:02d}{item.path.suffix.lower()}",
            "type": mime_for(item.path.name),
            "size": item.path.stat().st_size,
            "kind": item.kind,
        }
        orig_names.append(served)

    for meta in files.values():
        if "size" not in meta:
            meta["size"] = (workdir / meta["path"]).stat().st_size

    visual_names = [v.file for v in pack.visuals]
    packs = {
        "full": share_batches(visual_names, "post.txt"),
        "compact": [["post-compact.txt"] + [s for s, _ in pack.sheets]] if pack.sheets else None,
        "originals": [orig_names[i:i + 10] for i in range(0, len(orig_names), 10)],
    }
    transcript = "\n".join(
        v.transcript.text for v in pack.videos if v.transcript and v.transcript.segments
    )
    m = fetched.meta
    return {
        "meta": {
            "platform": m.platform, "url": m.url, "author": m.author, "author_name": m.author_name,
            "caption": m.caption, "date": m.date, "title": m.title,
        },
        "counts": {
            "images": sum(1 for i in fetched.items if i.kind == "image"),
            "videos": sum(1 for i in fetched.items if i.kind == "video"),
            "pictures": len(pack.visuals),
        },
        "files": files,
        "packs": packs,
        "transcript_preview": transcript[:600],
        "tool": fetched.tool,
        "notes": fetched.notes,
    }


class JobStore:
    # After job.json could not be written, the worker pauses before the next job: RETRY_DELAY
    # seconds, doubled with every further failure in a row, at most MAX_DELAY. No job is retried.
    RETRY_DELAY = 2.0
    MAX_DELAY = 60.0

    def __init__(self, settings: Settings, runner: Runner = default_runner):
        self.settings = settings
        self.runner = runner
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._worker: threading.Thread | None = None
        self._storage_failures = 0  # jobs in a row whose state could not be saved
        # What the last Instagram download said about the cookies ("ok" or "expired"), and when.
        self._cookies: tuple[str, float] = ("unknown", 0.0)

    # ---------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self.settings.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._load_existing()
        for target, name in ((self._work, "sharewerk-worker"), (self._janitor, "sharewerk-janitor")):
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)
        self._worker = self._threads[0]

    def stop(self) -> None:
        self._stop.set()
        self._queue.put("")  # wake the worker

    def _load_existing(self) -> None:
        cutoff = time.time() - self.settings.retention_hours * 3600
        for d in self.settings.jobs_dir.iterdir():
            if not d.is_dir():
                continue
            meta = d / "job.json"
            try:
                job = Job(**json.loads(meta.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError):
                shutil.rmtree(d, ignore_errors=True)
                continue
            if job.created < cutoff:
                shutil.rmtree(d, ignore_errors=True)
                continue
            if job.status not in TERMINAL:
                job.status, job.stage = "error", "done"
                job.error_code = "interrupted"
                try:
                    self._save(job)
                except StorageError as exc:
                    # The state is right in memory. Counting the failure makes the health check
                    # probe the volume until writing works again.
                    self._storage_failures += 1
                    log.error("%s", exc)
            self._jobs[job.id] = job
            self._note_cookies(job)  # so a restart keeps an "expired" alert

    # ------------------------------------------------------------------- public
    def submit(self, target: Target, force: bool = False) -> Job:
        """A new job, or the pending or finished one for the same link. A new job becomes known
        only after its job.json is saved: a failed save must leave nothing that a retry of the
        same link would find and that never runs. Raises StorageError."""
        with self._lock:
            if not force:
                for job in sorted(self._jobs.values(), key=lambda j: j.created, reverse=True):
                    if job.url == target.url and job.status != "error":
                        return job
            job = Job(uuid.uuid4().hex, target.url, target.platform, target.kind, target.key)
            try:
                self._save(job)  # creates the job's folder too
            except StorageError as exc:
                shutil.rmtree(self.workdir(job.id), ignore_errors=True)
                self._storage_failures += 1
                log.error("%s", exc)
                raise
            self._jobs[job.id] = job
        self._queue.put(job.id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def recent(self, limit: int = 10) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)[:limit]

    def queue_position(self, job_id: str) -> int:
        with self._lock:
            waiting = sorted(
                (j for j in self._jobs.values() if j.status == "queued"), key=lambda j: j.created
            )
            ids = [j.id for j in waiting]
            return ids.index(job_id) + 1 if job_id in ids else 0

    def workdir(self, job_id: str) -> Path:
        return self.settings.jobs_dir / job_id

    def cookie_state(self) -> str:
        """The cookies as the last Instagram download saw them, for the health check: "ok",
        "expired" (it asked for a login), "missing" (no cookie file) or "unknown" (no Instagram
        download since the cookie file was last written)."""
        try:
            written = self.settings.cookies_file.stat().st_mtime
        except OSError:
            return "missing"
        state, when = self._cookies
        if state != "unknown" and written > when:
            return "unknown"  # new cookies, not tried yet
        return state

    def _note_cookies(self, job: Job) -> None:
        # Only Instagram needs the cookies; a Facebook login error says nothing about them.
        if job.platform != "instagram":
            return
        if job.status == "done":
            state = "ok"
        elif job.status == "error" and job.error_code == "auth_required":
            state = "expired"
        else:
            return
        if job.updated >= self._cookies[1]:
            self._cookies = (state, job.updated)

    def problem(self) -> str:
        """Why jobs cannot be processed right now, or "" if they can (for the health check)."""
        if self._worker is None or not self._worker.is_alive():
            return "worker_stopped"
        if self._storage_failures:
            probe = self.settings.jobs_dir / ".write-test"
            try:
                probe.write_text("ok", encoding="utf-8")
                probe.unlink()
            except OSError:
                return STORAGE_FAILED
        return ""

    def file_path(self, job: Job, name: str) -> tuple[Path, dict] | None:
        if not job.result:
            return None
        meta = job.result["files"].get(name)
        if not meta:
            return None
        root = self.workdir(job.id).resolve()
        path = (root / meta["path"]).resolve()
        if root not in path.parents or not path.is_file():
            return None
        return path, meta

    # ----------------------------------------------------------------- internal
    def _save(self, job: Job) -> None:
        job.updated = time.time()
        path = self.workdir(job.id) / "job.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(job.public()), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            raise StorageError(f"cannot save the state of job {job.id}: {exc}") from exc

    def _update(self, job: Job, **changes) -> None:
        with self._lock:
            for k, v in changes.items():
                setattr(job, k, v)
            self._save(job)

    def _work(self) -> None:
        # Nothing may end this loop but stop(): a dead worker would leave every job queued.
        while not self._stop.is_set():
            job_id = self._queue.get()
            job = self.get(job_id) if job_id else None
            if job is None:
                continue
            try:
                self._process(job)
            except StorageError as exc:
                self._storage_failures += 1
                log.error("%s (%d job(s) in a row)", exc, self._storage_failures)
                self._give_up(job, STORAGE_FAILED, str(exc))
                pause = self.RETRY_DELAY * 2 ** (self._storage_failures - 1)
                self._stop.wait(min(self.MAX_DELAY, pause))
            except Exception as exc:  # noqa: BLE001 - keep the worker alive
                log.exception("job %s: unexpected error in the worker", job.id)
                self._give_up(job, "internal", str(exc))
            else:
                self._storage_failures = 0

    def _process(self, job: Job) -> None:
        self._update(job, status="running", stage="downloading")
        try:
            result = self.runner(job, self.workdir(job.id), self.settings, lambda s: self._update(job, stage=s))
        except StorageError:
            raise
        except FetchError as exc:
            self._update(job, status="error", stage="done", error_code=exc.code, error_detail=exc.detail[-1000:])
            self._note_cookies(job)
            log.warning("job %s failed: %s", job.id, exc.code)
            return
        except Exception as exc:  # noqa: BLE001 - report it as the job's error
            log.exception("job %s crashed", job.id)
            self._update(job, status="error", stage="done", error_code="internal", error_detail=str(exc)[-1000:])
            return
        self._update(job, status="done", stage="done", result=result)
        self._note_cookies(job)
        log.info("job %s done (%s)", job.id, job.url)

    def _give_up(self, job: Job, code: str, detail: str) -> None:
        """Mark a job as failed after its state could not be saved: in memory in any case, so
        the page shows the error instead of a job that stays queued, running or seemingly done."""
        with self._lock:
            if job.status != "error":  # a job that failed anyway keeps its own reason
                job.status, job.error_code, job.error_detail, job.result = "error", code, detail[-1000:], None
            job.stage = "done"
            try:
                self._save(job)
            except StorageError:
                pass  # already logged; job.json keeps the older state until a restart marks it interrupted

    def _janitor(self) -> None:
        while not self._stop.wait(1800):
            self.purge_expired()

    def purge_expired(self) -> int:
        cutoff = time.time() - self.settings.retention_hours * 3600
        removed = 0
        with self._lock:
            for job_id, job in list(self._jobs.items()):
                if job.created < cutoff and job.status in TERMINAL:
                    shutil.rmtree(self.workdir(job_id), ignore_errors=True)
                    del self._jobs[job_id]
                    removed += 1
        return removed
