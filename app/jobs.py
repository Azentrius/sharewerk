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
            "path": str(item.path.relative_to(workdir)),
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
    def __init__(self, settings: Settings, runner: Runner = default_runner):
        self.settings = settings
        self.runner = runner
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    # ---------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self.settings.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._load_existing()
        for target, name in ((self._work, "sharewerk-worker"), (self._janitor, "sharewerk-janitor")):
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)

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
                self._save(job)
            self._jobs[job.id] = job

    # ------------------------------------------------------------------- public
    def submit(self, target: Target, force: bool = False) -> Job:
        with self._lock:
            if not force:
                for job in sorted(self._jobs.values(), key=lambda j: j.created, reverse=True):
                    if job.url == target.url and job.status != "error":
                        return job
            job = Job(uuid.uuid4().hex, target.url, target.platform, target.kind, target.key)
            self._jobs[job.id] = job
            self.workdir(job.id).mkdir(parents=True, exist_ok=True)
            self._save(job)
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
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(job.public()), encoding="utf-8")
        tmp.replace(path)

    def _update(self, job: Job, **changes) -> None:
        with self._lock:
            for k, v in changes.items():
                setattr(job, k, v)
            self._save(job)

    def _work(self) -> None:
        while not self._stop.is_set():
            job_id = self._queue.get()
            job = self.get(job_id) if job_id else None
            if job is None:
                continue
            self._update(job, status="running", stage="downloading")
            try:
                result = self.runner(job, self.workdir(job.id), self.settings, lambda s: self._update(job, stage=s))
                self._update(job, status="done", stage="done", result=result)
                log.info("job %s done (%s)", job.id, job.url)
            except FetchError as exc:
                self._update(job, status="error", stage="done", error_code=exc.code, error_detail=exc.detail[-1000:])
                log.warning("job %s failed: %s", job.id, exc.code)
            except Exception as exc:  # noqa: BLE001 - report, keep the worker alive
                log.exception("job %s crashed", job.id)
                self._update(job, status="error", stage="done", error_code="internal", error_detail=str(exc)[-1000:])

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
