# SPDX-License-Identifier: Apache-2.0
"""Cookies per platform: the upload from the browser extension, what a download gets, and the
state per platform in /healthz."""

import logging
import os
import stat
import threading
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app import fetch as fetch_module
from app.cookies import for_download
from app.fetch import FetchError, FetchResult, MediaItem, PostMeta, fetch
from app.main import create_app
from app.urls import Target

from .conftest import TOKEN

EXTENSION = {"X-Sharewerk-Client": "extension"}
INSTAGRAM = Target("https://www.instagram.com/p/DPq1aBcXyZ_/", "instagram", "post", "DPq1aBcXyZ_")
FACEBOOK = Target("https://www.facebook.com/reel/954162721072206/", "facebook", "reel", "954162721072206")
# A cookie file put in place by hand with (fake) cookies of both platforms.
HAND_MADE = (
    "# Netscape HTTP Cookie File\n"
    ".instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\tfromfile\n"
    "#HttpOnly_.facebook.com\tTRUE\t/\tTRUE\t0\tc_user\tfromfile\n"
    ".facebook.com\tTRUE\t/\tTRUE\t0\txs\tfromfile\n"
)


def cookie(name: str, value: str = "test", domain: str = ".instagram.com", **extra) -> dict:
    """A cookie as chrome.cookies.getAll() returns it."""
    return {
        "domain": domain, "name": name, "value": value, "path": "/", "secure": True, "httpOnly": True,
        "hostOnly": False, "session": False, "expirationDate": 1893456000.5, "sameSite": "lax",
        "storeId": "0", **extra,
    }


INSTAGRAM_LOGIN = [cookie("sessionid"), cookie("ds_user_id", "12345"), cookie("csrftoken")]
FACEBOOK_LOGIN = [cookie("c_user", "678", ".facebook.com"), cookie("xs", "test", ".facebook.com")]


def runner(job, workdir, settings, set_stage):
    if "LOGIN" in job.url:
        raise FetchError("auth_required", "login required")
    return {"files": {}, "packs": {}, "meta": {}, "counts": {}, "incomplete": ""}


def client_for(settings, **changes) -> TestClient:
    s = replace(settings, auth_mode="none", **changes)
    return TestClient(create_app(s, runner=runner), base_url="https://testserver")


def put(client, platform: str, cookies, headers=EXTENSION):
    return client.put(f"/api/cookies/{platform}", json={"cookies": cookies}, headers=headers)


def run(client, url: str) -> dict:
    job_id = client.post("/api/jobs", json={"url": url}).json()["id"]
    deadline = time.time() + 5
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"done", "error"}:
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def code(response) -> str:
    return response.json()["detail"]["code"]


# ------------------------------------------------------------------- upload

def test_the_extension_sends_the_cookies_of_one_platform(settings):
    with client_for(settings) as client:
        r = put(client, "instagram", INSTAGRAM_LOGIN)
        assert r.status_code == 200
        body = r.json()
        assert (body["platform"], body["state"], body["source"]) == ("instagram", "unknown", "extension")
        assert body["updated"] > 0

        path = settings.cookies_dir / "instagram.txt"
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "# Netscape HTTP Cookie File"
        assert ".instagram.com\tTRUE\t/\tTRUE\t1893456000\tsessionid\ttest" in lines
        assert len([line for line in lines if not line.startswith("#")]) == 3
        if os.name == "posix":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
            assert stat.S_IMODE(settings.cookies_dir.stat().st_mode) == 0o700

        platforms = client.get("/api/cookies").json()["platforms"]
        assert platforms["instagram"]["source"] == "extension"
        assert platforms["facebook"] == {"state": "missing", "source": "", "updated": None}


def test_host_only_and_session_cookies_keep_their_meaning(settings):
    cookies = [
        cookie("c_user", "678", "www.facebook.com", hostOnly=True),
        cookie("xs", "test", ".facebook.com", expirationDate=None, session=True, secure=False),
    ]
    with client_for(settings) as client:
        assert put(client, "facebook", cookies).status_code == 200
    lines = (settings.cookies_dir / "facebook.txt").read_text(encoding="utf-8").splitlines()
    assert "www.facebook.com\tFALSE\t/\tTRUE\t1893456000\tc_user\t678" in lines
    assert ".facebook.com\tTRUE\t/\tFALSE\t0\txs\ttest" in lines


@pytest.mark.parametrize("domain", [".facebook.com", ".evilinstagram.com", "instagram.com.example.net", ".example.net"])
def test_cookies_of_another_site_are_refused(settings, domain):
    with client_for(settings) as client:
        r = put(client, "instagram", INSTAGRAM_LOGIN + [cookie("other", "test", domain)])
        assert (r.status_code, code(r)) == (422, "cookie_domain")
    assert not (settings.cookies_dir / "instagram.txt").exists()


def test_cookies_without_a_login_are_refused(settings):
    with client_for(settings) as client:
        r = put(client, "instagram", [cookie("csrftoken"), cookie("mid")])
        assert (r.status_code, code(r)) == (422, "cookie_session_missing")
        r = put(client, "facebook", [cookie("c_user", "678", ".facebook.com")])
        assert (r.status_code, code(r)) == (422, "cookie_session_missing")
    assert not settings.cookies_dir.exists() or not any(settings.cookies_dir.iterdir())


@pytest.mark.parametrize("field,value", [
    ("value", "test\n.example.net\tTRUE\t/\tTRUE\t0\tsessionid\tx"),  # would add a line
    ("name", "session\tid"),
    ("path", "/\r"),
    ("value", "x" * 5000),
    ("name", ""),
    ("value", 12),
])
def test_a_field_that_could_break_the_file_is_refused(settings, field, value):
    broken = cookie("sessionid", **{field: value}) if field != "name" else {**cookie("sessionid"), "name": value}
    with client_for(settings) as client:
        r = put(client, "instagram", [broken, cookie("ds_user_id", "12345")])
        assert (r.status_code, code(r)) == (422, "cookies_invalid")
    assert not (settings.cookies_dir / "instagram.txt").exists()


@pytest.mark.parametrize("value", ["abc def", "abc\u0085def", "café"])
def test_only_printable_ascii_reaches_the_file(settings, value):
    # Python's splitlines() also splits at U+2028 and U+0085: such a value would be cut short
    # in the copy a download gets.
    with client_for(settings) as client:
        r = put(client, "instagram", [cookie("sessionid", value)])
        assert (r.status_code, code(r)) == (422, "cookies_invalid")


@pytest.mark.parametrize("body", [
    b'{"cookies": [{"domain": ".instagram.com", "name": "sessionid", "value": "x", "expirationDate": Infinity}]}',
    b'{"cookies": [{"domain": ".instagram.com", "name": "sessionid", "value": "x", "expirationDate": NaN}]}',
    b'{"cookies": [{"domain": ".instagram.com", "name": "sessionid", "value": "x", "expirationDate": 1e300}]}',
    b'{"cookies": [{"domain": ".instagram.com", "name": "sessionid", "value": "x", "expirationDate": -5}]}',
    b'{"cookies": [{"domain": ".instagram.com", "name": "sessionid", "value": "x", "expirationDate": "soon"}]}',
    b"[" * 50000,
], ids=["infinity", "nan", "huge", "negative", "text", "deep-nesting"])
def test_unusable_numbers_and_deep_nesting_are_refused_not_a_server_error(settings, body):
    with client_for(settings) as client:
        r = client.put("/api/cookies/instagram", content=body, headers=EXTENSION)
        assert (r.status_code, code(r)) == (422, "cookies_invalid")


def test_malformed_requests_are_refused(settings):
    with client_for(settings) as client:
        r = put(client, "tiktok", INSTAGRAM_LOGIN)
        assert (r.status_code, code(r)) == (404, "platform_unknown")
        r = put(client, "instagram", [])
        assert (r.status_code, code(r)) == (422, "cookies_invalid")
        r = put(client, "instagram", [cookie("sessionid")] * 101)
        assert (r.status_code, code(r)) == (422, "cookies_invalid")
        r = client.put("/api/cookies/instagram", content=b"{not json", headers=EXTENSION)
        assert (r.status_code, code(r)) == (422, "cookies_invalid")
        r = client.put("/api/cookies/instagram", json=["sessionid"], headers=EXTENSION)
        assert (r.status_code, code(r)) == (422, "cookies_invalid")
        r = client.put("/api/cookies/instagram", content=b" " * (512 * 1024 + 1), headers=EXTENSION)
        assert (r.status_code, code(r)) == (413, "cookies_too_large")


def test_requests_without_the_extension_header_are_refused(settings):
    # A web page cannot send this header to another site without a CORS preflight.
    with client_for(settings) as client:
        r = put(client, "instagram", INSTAGRAM_LOGIN, headers={})
        assert (r.status_code, code(r)) == (403, "client_header_missing")
        r = put(client, "instagram", INSTAGRAM_LOGIN, headers={"X-Sharewerk-Client": "page"})
        assert (r.status_code, code(r)) == (403, "client_header_missing")
        assert put(client, "instagram", INSTAGRAM_LOGIN).status_code == 200
        r = client.delete("/api/cookies/instagram")
        assert (r.status_code, code(r)) == (403, "client_header_missing")
    assert (settings.cookies_dir / "instagram.txt").exists()


def test_the_upload_needs_the_login_of_the_app(settings):
    with TestClient(create_app(settings, runner=runner), base_url="https://testserver") as client:
        assert put(client, "instagram", INSTAGRAM_LOGIN).status_code == 401
        assert client.get("/api/cookies").status_code == 401
        r = put(client, "instagram", INSTAGRAM_LOGIN, headers={**EXTENSION, "Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 200


def test_cookie_values_never_reach_answers_or_logs(settings, caplog):
    caplog.set_level(logging.DEBUG)
    secret = "SECRETVALUE123"
    with client_for(settings) as client:
        refused = put(client, "instagram", [cookie("sessionid", secret), cookie("x", secret, ".example.net")])
        broken = put(client, "instagram", [cookie("sessionid", secret + "\n")])
        accepted = put(client, "instagram", [cookie("sessionid", secret)])
        listed = client.get("/api/cookies")
    assert refused.status_code == 422 and broken.status_code == 422 and accepted.status_code == 200
    for response in (refused, broken, accepted, listed):
        assert secret not in response.text
    assert secret not in caplog.text


def test_deleting_the_sent_cookies(settings):
    with client_for(settings) as client:
        put(client, "facebook", FACEBOOK_LOGIN)
        r = client.delete("/api/cookies/facebook", headers=EXTENSION)
        assert r.status_code == 200
        assert (r.json()["state"], r.json()["source"]) == ("missing", "")
        assert not (settings.cookies_dir / "facebook.txt").exists()
        r = client.delete("/api/cookies/facebook", headers=EXTENSION)
        assert (r.status_code, code(r)) == (404, "cookies_not_found")


def test_a_volume_that_cannot_be_written_answers_503(settings):
    settings.data_dir.mkdir(parents=True)
    settings.cookies_dir.write_text("a file where the folder should be", encoding="utf-8")
    with client_for(settings) as client:
        r = put(client, "instagram", INSTAGRAM_LOGIN)
        assert (r.status_code, code(r)) == (503, "storage_failed")


# ------------------------------------------------------------ what a download gets

def test_a_download_gets_the_sent_cookies_before_the_hand_made_file(settings, tmp_path):
    hand_made = tmp_path / "cookies.txt"
    hand_made.write_text(HAND_MADE, encoding="utf-8")
    s = replace(settings, cookies_file=hand_made)
    with client_for(settings, cookies_file=hand_made) as client:
        put(client, "instagram", [cookie("sessionid", "fromextension")])

    dest = for_download(s, "instagram", tmp_path / "instagram-job.txt")
    text = dest.read_text(encoding="utf-8")
    assert "fromextension" in text and "fromfile" not in text and "facebook" not in text


def test_a_download_gets_only_the_lines_of_its_platform_from_the_hand_made_file(settings, tmp_path):
    hand_made = tmp_path / "cookies.txt"
    hand_made.write_text(HAND_MADE, encoding="utf-8")
    s = replace(settings, cookies_file=hand_made)

    facebook = for_download(s, "facebook", tmp_path / "facebook-job.txt").read_text(encoding="utf-8").splitlines()
    assert facebook == [
        "# Netscape HTTP Cookie File",
        "#HttpOnly_.facebook.com\tTRUE\t/\tTRUE\t0\tc_user\tfromfile",
        ".facebook.com\tTRUE\t/\tTRUE\t0\txs\tfromfile",
    ]
    instagram = for_download(s, "instagram", tmp_path / "instagram-job.txt").read_text(encoding="utf-8")
    assert "instagram.com" in instagram and "facebook.com" not in instagram


def test_no_cookie_file_for_a_platform_without_cookies(settings, tmp_path):
    hand_made = tmp_path / "cookies.txt"
    hand_made.write_text("# Netscape HTTP Cookie File\n.instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\tx\n", encoding="utf-8")
    s = replace(settings, cookies_file=hand_made)
    assert for_download(s, "facebook", tmp_path / "facebook-job.txt") is None
    assert not (tmp_path / "facebook-job.txt").exists()
    assert for_download(settings, "instagram", tmp_path / "instagram-job.txt") is None


def test_fetch_hands_the_tool_the_cookies_of_the_post_platform_and_removes_the_copy(settings, tmp_path, monkeypatch):
    hand_made = tmp_path / "cookies.txt"
    hand_made.write_text(HAND_MADE, encoding="utf-8")
    seen = []

    def tool(target, raw, cookies, s):
        seen.append(cookies.read_text(encoding="utf-8") if cookies else None)
        image = raw / "1.jpg"
        image.write_bytes(b"jpeg")
        return FetchResult([MediaItem(image, "image", 1)], PostMeta(target.platform, target.url), "fake")

    monkeypatch.setattr(fetch_module, "run_yt_dlp", tool)
    monkeypatch.setattr(fetch_module, "run_gallery_dl", tool)
    fetch(FACEBOOK, tmp_path / "job", replace(settings, cookies_file=hand_made))

    assert "c_user" in seen[0] and "instagram.com" not in seen[0]
    assert not (tmp_path / "job" / "cookies.txt").exists()


# --------------------------------------------------------------- state per platform

def test_the_health_check_has_a_state_per_platform(settings):
    with client_for(settings) as client:
        put(client, "facebook", FACEBOOK_LOGIN)
        health = client.get("/healthz").json()
        assert health["cookies"] == "missing"  # Instagram, as before
        assert health["cookie_states"] == {"instagram": "missing", "facebook": "unknown"}

        assert run(client, "https://www.facebook.com/reel/1LOGIN/")["error_code"] == "auth_required"
        health = client.get("/healthz").json()
        assert health["cookie_states"]["facebook"] == "expired"
        assert health["cookies"] == "missing"  # a Facebook login error says nothing about Instagram

        time.sleep(0.01)
        put(client, "facebook", FACEBOOK_LOGIN)  # sent again after a new login
        assert client.get("/healthz").json()["cookie_states"]["facebook"] == "unknown"

        put(client, "instagram", INSTAGRAM_LOGIN)
        assert run(client, "https://www.instagram.com/p/works/")["status"] == "done"
        health = client.get("/healthz").json()
        assert (health["cookies"], health["cookie_states"]["instagram"]) == ("ok", "ok")
        assert client.get("/api/cookies").json()["platforms"]["instagram"]["state"] == "ok"


def test_cookies_that_arrive_while_a_download_runs_are_not_judged_by_it(settings):
    # A login error makes you log in again; the new cookies arrive while a job that still has the
    # old ones runs. Its login error must not mark the new cookies expired.
    started, release = threading.Event(), threading.Event()

    def slow(job, workdir, s, set_stage):
        started.set()
        release.wait(5)
        return runner(job, workdir, s, set_stage)

    s = replace(settings, auth_mode="none")
    with TestClient(create_app(s, runner=slow), base_url="https://testserver") as client:
        put(client, "instagram", INSTAGRAM_LOGIN)
        job_id = client.post("/api/jobs", json={"url": "https://www.instagram.com/p/LOGIN1/"}).json()["id"]
        assert started.wait(5)
        time.sleep(0.01)
        put(client, "instagram", [cookie("sessionid", "new")])  # sent while the job runs
        release.set()
        deadline = time.time() + 5
        while client.get(f"/api/jobs/{job_id}").json()["status"] != "error" and time.time() < deadline:
            time.sleep(0.02)
        assert client.get("/healthz").json()["cookies"] == "unknown"

        job = run(client, "https://www.instagram.com/p/works/")  # the next download tries them
        assert job["status"] == "done"
        assert client.get("/healthz").json()["cookies"] == "ok"


def test_an_unreadable_hand_made_file_is_reported_without_its_content(settings, tmp_path, caplog):
    hand_made = tmp_path / "cookies.txt"
    hand_made.write_bytes(b"# Netscape HTTP Cookie File\n.instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\t\xffSECRET\n")
    with client_for(settings, cookies_file=hand_made) as client:
        for _ in range(3):
            assert client.get("/healthz").json()["cookies"] == "missing"
    warnings = [r for r in caplog.records if "cannot read the cookie file" in r.getMessage()]
    assert len(warnings) == 1  # once per version of the file, not on every health check
    assert "SECRET" not in caplog.text


def test_a_hand_made_file_without_cookies_of_a_platform_counts_as_missing(settings, tmp_path):
    hand_made = tmp_path / "cookies.txt"
    hand_made.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    with client_for(settings, cookies_file=hand_made) as client:
        assert client.get("/healthz").json()["cookie_states"] == {"instagram": "missing", "facebook": "missing"}
