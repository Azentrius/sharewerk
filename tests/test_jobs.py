# SPDX-License-Identifier: Apache-2.0
"""The job worker when job.json cannot be written. The errors are simulated (ENOSPC on purpose),
no disk is filled."""

import errno
import json
import threading
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.fetch import FetchError
from app.jobs import Job, JobStore
from app.main import create_app
from app.urls import Target

from .conftest import TOKEN

real_write_text = Path.write_text


class Disk:
    """Lets writes below the data directory fail like a full disk: once for a given job state,
    or all of them while `full` is set. Counts every attempt to write a job state."""

    def __init__(self, monkeypatch, data_dir: Path):
        self.data_dir = str(data_dir)
        self.full = False
        self.fail_next: set[str] = set()
        self.attempts: list[tuple[str, str]] = []
        disk = self

        def write_text(path, data, *args, **kwargs):
            if str(path).startswith(disk.data_dir):
                status = json.loads(data).get("status", "") if path.name == "job.tmp" else ""
                if path.name == "job.tmp":
                    disk.attempts.append((path.parent.name, status))
                if disk.full or status in disk.fail_next:
                    disk.fail_next.discard(status)
                    raise OSError(errno.ENOSPC, "No space left on device", str(path))
            return real_write_text(path, data, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", write_text)

    def fail_once(self, status: str) -> None:
        self.fail_next.add(status)


release = threading.Event()


def runner(job, workdir, settings, set_stage):
    if "WAIT" in job.url:
        release.wait(10)
    if "FAILS" in job.url:
        raise FetchError("auth_required", "[instagram][error] 401 Unauthorized")
    set_stage("processing")
    return {"files": {}, "packs": {}, "meta": {}, "counts": {}}


def target(key: str) -> Target:
    return Target(f"https://www.instagram.com/p/{key}/", "instagram", "post", key)


def finished(store: JobStore, job_id: str, timeout: float = 5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = store.get(job_id)
        if job.status in {"done", "error"}:
            return job
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} is still {store.get(job_id).status}: the worker stopped")


@pytest.fixture(autouse=True)
def short_pause(monkeypatch):
    monkeypatch.setattr(JobStore, "RETRY_DELAY", 0.01, raising=False)
    release.clear()
    yield
    release.set()


@pytest.fixture
def disk(monkeypatch, settings) -> Disk:
    return Disk(monkeypatch, settings.data_dir)


@pytest.fixture
def store(settings, disk):
    s = JobStore(settings, runner)
    s.start()
    yield s
    s.stop()


def test_write_error_when_a_job_starts(store, disk):
    disk.fail_once("running")
    first = finished(store, store.submit(target("first")).id)
    assert (first.status, first.error_code) == ("error", "storage_failed")
    assert disk.attempts.count((first.id, "running")) == 1  # no retry loop

    second = finished(store, store.submit(target("second")).id)
    assert second.status == "done"


def test_write_error_when_a_job_finishes(store, disk):
    disk.fail_once("done")
    first = finished(store, store.submit(target("first")).id)
    # Not "done": the result is not saved, so a restart would lose it.
    assert (first.status, first.error_code, first.result) == ("error", "storage_failed", None)
    saved = json.loads((store.workdir(first.id) / "job.json").read_text(encoding="utf-8"))
    assert (saved["status"], saved["error_code"]) == ("error", "storage_failed")

    second = finished(store, store.submit(target("second")).id)
    assert second.status == "done"


def test_write_error_when_saving_the_error_state(store, disk):
    disk.fail_once("error")
    first = finished(store, store.submit(target("FAILS")).id)
    assert (first.status, first.error_code) == ("error", "auth_required")
    assert disk.attempts.count((first.id, "error")) <= 2

    second = finished(store, store.submit(target("second")).id)
    assert second.status == "done"


def test_health_reports_storage_failures_and_recovers(settings, disk):
    with TestClient(create_app(settings, runner=runner), base_url="https://testserver") as client:
        client.headers["Authorization"] = f"Bearer {TOKEN}"
        store = client.app.state.store
        assert client.get("/healthz").json() == {"ok": True, "cookies": "missing"}

        job_id = client.post("/api/jobs", json={"url": "https://www.instagram.com/p/WAIT/"}).json()["id"]
        disk.full = True  # the disk fills up while the post is being prepared
        release.set()
        job = finished(store, job_id)
        assert (job.status, job.error_code) == ("error", "storage_failed")
        assert client.get(f"/api/jobs/{job_id}").json()["status"] == "error"

        health = client.get("/healthz")
        assert health.status_code == 503
        assert health.json()["ok"] is False

        disk.full = False  # space was freed
        assert client.get("/healthz").json() == {"ok": True, "cookies": "missing"}
        again = client.post("/api/jobs", json={"url": "https://www.instagram.com/p/second/"}).json()["id"]
        assert finished(store, again).status == "done"


def persisted_queued_job(settings, key: str) -> str:
    """A job that was queued when the server went down, as job.json on the data volume."""
    job = Job(uuid.uuid4().hex, f"https://www.instagram.com/p/{key}/", "instagram", "post", key)
    directory = settings.jobs_dir / job.id
    directory.mkdir(parents=True)
    real_write_text(directory / "job.json", json.dumps(job.public()), encoding="utf-8")
    return job.id


def test_restart_while_storage_still_fails_is_unhealthy_until_it_works(settings, disk):
    interrupted = persisted_queued_job(settings, "interrupted")
    disk.full = True  # the disk is still full when the server starts again
    with TestClient(create_app(settings, runner=runner), base_url="https://testserver") as client:
        client.headers["Authorization"] = f"Bearer {TOKEN}"
        restored = client.get(f"/api/jobs/{interrupted}").json()
        assert (restored["status"], restored["error_code"]) == ("error", "interrupted")

        health = client.get("/healthz")
        assert health.status_code == 503
        assert health.json() == {"ok": False, "problem": "storage_failed", "cookies": "missing"}

        disk.full = False  # space was freed, no restart
        assert client.get("/healthz").json() == {"ok": True, "cookies": "missing"}
        job_id = client.post("/api/jobs", json={"url": "https://www.instagram.com/p/after/"}).json()["id"]
        assert finished(client.app.state.store, job_id).status == "done"


def test_failed_submit_leaves_no_job_behind_and_the_retry_is_processed(settings, disk):
    url = "https://www.instagram.com/p/retried/"
    app = create_app(settings, runner=runner)
    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as client:
        client.headers["Authorization"] = f"Bearer {TOKEN}"
        store = client.app.state.store

        disk.full = True
        failed = client.post("/api/jobs", json={"url": url})
        assert failed.status_code == 503
        assert failed.json()["detail"]["code"] == "storage_failed"
        assert client.get("/api/jobs").json() == []  # nothing that waits forever
        assert [p for p in settings.jobs_dir.iterdir() if p.is_dir()] == []
        assert client.get("/healthz").json() == {"ok": False, "problem": "storage_failed", "cookies": "missing"}

        disk.full = False
        retry = client.post("/api/jobs", json={"url": url})  # the same link, without force
        assert retry.status_code == 200
        job = finished(store, retry.json()["id"])
        assert job.status == "done"
        assert client.get("/healthz").json() == {"ok": True, "cookies": "missing"}


def test_duplicates_of_running_and_finished_jobs_are_still_reused(store):
    first = store.submit(target("WAIT"))
    deadline = time.time() + 5
    while store.get(first.id).status != "running" and time.time() < deadline:
        time.sleep(0.02)
    assert store.submit(target("WAIT")).id == first.id  # running
    release.set()
    assert finished(store, first.id).status == "done"
    assert store.submit(target("WAIT")).id == first.id  # done
    assert store.submit(target("WAIT"), force=True).id != first.id


def test_health_reports_a_stopped_worker(settings, disk):
    with TestClient(create_app(settings, runner=runner), base_url="https://testserver") as client:
        store = client.app.state.store
        store.stop()
        deadline = time.time() + 5
        while time.time() < deadline and client.get("/healthz").status_code == 200:
            time.sleep(0.02)
        health = client.get("/healthz")
        assert health.status_code == 503
        assert health.json()["ok"] is False
