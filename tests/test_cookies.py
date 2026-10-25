# SPDX-License-Identifier: Apache-2.0
"""The cookie state in /healthz: what the last Instagram download said about the cookies."""

import json
import os
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import fetch as fetch_module
from app.fetch import FetchError
from app.jobs import Job
from app.main import create_app

INSTAGRAM = "https://www.instagram.com/p/{}/"
FACEBOOK = "https://www.facebook.com/reel/{}/"
# A cookie file put in place by hand, with (fake) Instagram cookies only.
INSTAGRAM_COOKIES = "# Netscape HTTP Cookie File\n.instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\ttest\n"


def runner(job, workdir, settings, set_stage):
    if "LOGIN" in job.url:
        raise FetchError("auth_required", "[instagram][error] 401 Unauthorized")
    incomplete = "rate_limited" if "RATELIMITED" in job.url else ""
    return {"files": {}, "packs": {}, "meta": {}, "counts": {}, "incomplete": incomplete}


@pytest.fixture
def cookies(tmp_path):
    path = tmp_path / "cookies.txt"
    path.write_text(INSTAGRAM_COOKIES, encoding="utf-8")
    old = time.time() - 3600  # exported an hour ago
    os.utime(path, (old, old))
    return path


def run(client, url: str) -> dict:
    job_id = client.post("/api/jobs", json={"url": url}).json()["id"]
    deadline = time.time() + 5
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"done", "error"}:
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def health(client) -> tuple[int, dict]:
    """Status and body of /healthz; "cookies" is the Instagram entry of "cookie_states"."""
    r = client.get("/healthz")
    body = r.json()
    states = body.pop("cookie_states")
    assert states["instagram"] == body["cookies"]
    return r.status_code, body


def app_client(settings):
    return TestClient(create_app(replace(settings, auth_mode="none"), runner=runner), base_url="https://testserver")


def test_without_a_cookie_file_the_state_is_missing(settings):
    with app_client(settings) as client:
        assert health(client) == (200, {"ok": True, "cookies": "missing"})


def test_expired_cookies_are_reported_without_failing_the_health_check(settings, cookies):
    with app_client(replace(settings, cookies_file=cookies)) as client:
        assert health(client) == (200, {"ok": True, "cookies": "unknown"})

        assert run(client, INSTAGRAM.format("LOGIN1"))["error_code"] == "auth_required"
        assert health(client) == (200, {"ok": True, "cookies": "expired"})

        # A Facebook login error says nothing about the Instagram cookies.
        assert run(client, FACEBOOK.format("1"))["status"] == "done"
        assert run(client, FACEBOOK.format("LOGIN2"))["error_code"] == "auth_required"
        assert health(client)[1]["cookies"] == "expired"

        assert run(client, INSTAGRAM.format("works"))["status"] == "done"
        assert health(client) == (200, {"ok": True, "cookies": "ok"})


def test_new_cookies_clear_the_expired_state(settings, cookies):
    with app_client(replace(settings, cookies_file=cookies)) as client:
        run(client, INSTAGRAM.format("LOGIN1"))
        assert health(client)[1]["cookies"] == "expired"

        now = time.time() + 1  # cookies exported again
        os.utime(cookies, (now, now))
        assert health(client)[1]["cookies"] == "unknown"


def persisted(settings, url: str, status: str, error_code: str = "", age: float = 600) -> None:
    job = Job(uuid.uuid4().hex, url, "instagram", "post", "key", status=status, stage="done", error_code=error_code)
    job.created = job.updated = time.time() - age
    directory = settings.jobs_dir / job.id
    directory.mkdir(parents=True)
    (directory / "job.json").write_text(json.dumps(job.public()), encoding="utf-8")


def test_the_state_survives_a_restart(settings, cookies):
    s = replace(settings, cookies_file=cookies)
    old = time.time() - 7200  # cookies exported before both jobs
    os.utime(cookies, (old, old))
    persisted(s, INSTAGRAM.format("early"), "done", age=1200)
    persisted(s, INSTAGRAM.format("LOGIN"), "error", "auth_required", age=600)
    with app_client(s) as client:
        assert health(client)[1]["cookies"] == "expired"


def test_cookies_newer_than_the_last_verdict_are_unknown_after_a_restart(settings, cookies):
    s = replace(settings, cookies_file=cookies)
    persisted(s, INSTAGRAM.format("LOGIN"), "error", "auth_required", age=7200)  # before the export
    with app_client(s) as client:
        assert health(client)[1]["cookies"] == "unknown"


def test_a_pack_cut_short_by_a_rate_limit_still_means_the_cookies_work(settings, cookies):
    with app_client(replace(settings, cookies_file=cookies)) as client:
        job = run(client, INSTAGRAM.format("RATELIMITED"))
        assert (job["status"], job["result"]["incomplete"]) == ("done", "rate_limited")
        assert health(client) == (200, {"ok": True, "cookies": "ok"})


FAKE = Path(__file__).with_name("fake_downloader.py")


def test_a_partial_pack_after_a_login_error_reports_expired_cookies(settings, cookies, monkeypatch):
    # Real download, pack and job: gallery-dl gets one real image and then needs a login,
    # yt-dlp needs a login right away. The one image becomes a pack marked incomplete.
    monkeypatch.setattr(fetch_module, "_tool", lambda name: [sys.executable, str(FAKE), name])
    for key, value in {
        "FAKE_GALLERY_DL_FILES": "1", "FAKE_GALLERY_DL_JPEG": "1", "FAKE_GALLERY_DL_EXIT": "16",
        "FAKE_GALLERY_DL_STDERR": "[instagram][error] AuthRequired: login required\n",
        "FAKE_YT_DLP_FILES": "0", "FAKE_YT_DLP_EXIT": "1",
        "FAKE_YT_DLP_STDERR": "ERROR: [instagram] DPq1aBcXyZ_: login required\n",
    }.items():
        monkeypatch.setenv(key, value)
    s = replace(settings, auth_mode="none", cookies_file=cookies)

    with TestClient(create_app(s), base_url="https://testserver") as client:
        job = run(client, INSTAGRAM.format("DPq1aBcXyZ_"))
        assert (job["status"], job["result"]["incomplete"]) == ("done", "auth_required")
        assert job["result"]["counts"]["pictures"] == 1  # the pack is there
        assert client.get(f"/api/jobs/{job['id']}/files/01.jpg").status_code == 200
        assert health(client) == (200, {"ok": True, "cookies": "expired"})

    with TestClient(create_app(s), base_url="https://testserver") as client:  # after a restart
        assert health(client) == (200, {"ok": True, "cookies": "expired"})
