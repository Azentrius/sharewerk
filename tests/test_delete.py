# SPDX-License-Identifier: Apache-2.0
"""Deleting a result right away instead of waiting for SHAREWERK_RETENTION_HOURS."""

import errno
import shutil
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import jobs as jobs_module
from app.main import create_app

from .conftest import TOKEN

release = threading.Event()


def runner(job, workdir, settings, set_stage):
    if "WAIT" in job.url:
        release.wait(5)
    (workdir / "out").mkdir(parents=True, exist_ok=True)
    (workdir / "out" / "post.txt").write_text("text", encoding="utf-8")
    (workdir / "out" / "01.jpg").write_bytes(b"picture")
    files = {"01.jpg": {"path": "out/01.jpg", "name": "x-01.jpg", "type": "image/jpeg", "size": 7}}
    return {"files": files, "packs": {}, "meta": {}, "counts": {}}


@pytest.fixture
def client(settings):
    release.clear()
    with TestClient(create_app(settings, runner=runner), base_url="https://testserver") as c:
        c.headers["Authorization"] = f"Bearer {TOKEN}"
        yield c
    release.set()


def submit(client, key: str) -> str:
    return client.post("/api/jobs", json={"url": f"https://www.instagram.com/p/{key}/"}).json()["id"]


def finished(client, job_id: str) -> dict:
    deadline = time.time() + 5
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"done", "error"}:
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_a_finished_result_is_deleted_with_its_files(client, settings):
    job_id = submit(client, "first")
    finished(client, job_id)
    assert (settings.jobs_dir / job_id / "out" / "post.txt").is_file()

    r = client.delete(f"/api/jobs/{job_id}")
    assert r.status_code == 200 and r.json() == {"deleted": job_id}
    assert not (settings.jobs_dir / job_id).exists()
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert [j["id"] for j in client.get("/api/jobs").json()] == []

    # The same link is prepared anew, not answered with the deleted job.
    again = submit(client, "first")
    assert again != job_id
    assert finished(client, again)["status"] == "done"


def test_a_running_job_cannot_be_deleted(client, settings):
    job_id = submit(client, "WAIT")
    r = client.delete(f"/api/jobs/{job_id}")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "job_busy"
    release.set()
    assert finished(client, job_id)["status"] == "done"
    assert client.delete(f"/api/jobs/{job_id}").status_code == 200


def test_an_unknown_job(client):
    r = client.delete("/api/jobs/deadbeef")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "job_not_found"


def test_a_delete_that_stops_halfway_leaves_no_reusable_result(client, settings, monkeypatch):
    job_id = submit(client, "first")
    finished(client, job_id)
    assert client.get(f"/api/jobs/{job_id}/files/01.jpg").status_code == 200
    real_rmtree = shutil.rmtree

    def rmtree(path, *args, **kwargs):
        if str(path).endswith(job_id):  # the picture goes, then the rest fails
            (settings.jobs_dir / job_id / "out" / "01.jpg").unlink()
            raise PermissionError(13, "Permission denied", str(path))
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(jobs_module.shutil, "rmtree", rmtree)
    r = client.delete(f"/api/jobs/{job_id}")
    assert r.status_code == 503 and r.json()["detail"]["code"] == "storage_failed"

    broken = client.get(f"/api/jobs/{job_id}").json()
    assert (broken["status"], broken["error_code"], broken["result"]) == ("error", "delete_failed", None)
    assert client.get(f"/api/jobs/{job_id}/files/01.jpg").status_code == 404
    again = submit(client, "first")  # the same link, without force: not the broken result
    assert again != job_id
    assert finished(client, again)["status"] == "done"
    monkeypatch.setattr(jobs_module.shutil, "rmtree", real_rmtree)


def test_a_half_deleted_result_can_be_deleted_after_a_restart(settings, monkeypatch):
    with TestClient(create_app(settings, runner=runner), base_url="https://testserver") as c:
        c.headers["Authorization"] = f"Bearer {TOKEN}"
        job_id = submit(c, "first")
        finished(c, job_id)
        real_rmtree = shutil.rmtree

        def rmtree(path, *args, **kwargs):
            if str(path).endswith(job_id):
                (settings.jobs_dir / job_id / "out" / "01.jpg").unlink()
                raise PermissionError(13, "Permission denied", str(path))
            return real_rmtree(path, *args, **kwargs)

        monkeypatch.setattr(jobs_module.shutil, "rmtree", rmtree)
        assert c.delete(f"/api/jobs/{job_id}").status_code == 503
        monkeypatch.setattr(jobs_module.shutil, "rmtree", real_rmtree)

    with TestClient(create_app(settings, runner=runner), base_url="https://testserver") as c:
        c.headers["Authorization"] = f"Bearer {TOKEN}"
        job = c.get(f"/api/jobs/{job_id}").json()
        assert (job["status"], job["error_code"]) == ("error", "delete_failed")
        assert c.post("/api/jobs", json={"url": "https://www.instagram.com/p/first/"}).json()["id"] != job_id
        assert c.delete(f"/api/jobs/{job_id}").status_code == 200  # a further attempt finishes the job
        assert not (settings.jobs_dir / job_id).exists()


def test_nothing_is_removed_when_the_job_cannot_be_marked_first(client, settings, monkeypatch):
    job_id = submit(client, "first")
    finished(client, job_id)
    real_write_text = Path.write_text

    def write_text(path, data, *args, **kwargs):
        if path.name == "job.tmp":
            raise OSError(errno.ENOSPC, "No space left on device", str(path))
        return real_write_text(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write_text)
    assert client.delete(f"/api/jobs/{job_id}").status_code == 503
    monkeypatch.setattr(Path, "write_text", real_write_text)
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "done"
    assert client.get(f"/api/jobs/{job_id}/files/01.jpg").status_code == 200


def test_deleting_needs_a_login(settings):
    with TestClient(create_app(replace(settings), runner=runner), base_url="https://testserver") as c:
        assert c.delete("/api/jobs/deadbeef").status_code == 401
