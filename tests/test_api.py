# SPDX-License-Identifier: Apache-2.0
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app import jobs as jobs_module
from app.fetch import FetchError, FetchResult, MediaItem, PostMeta
from app.main import create_app, safe_next

from .conftest import TOKEN, make_image

POST = "https://www.instagram.com/p/DPq1aBcXyZ_/?igsh=abc"


@pytest.fixture
def fake_fetch(monkeypatch):
    calls = []

    def _fetch(target, workdir, settings):
        calls.append(target.url)
        if "FAILS" in target.url:
            raise FetchError("auth_required", "[instagram][error] 401 Unauthorized")
        raw = workdir / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        items = [MediaItem(make_image(raw / f"{i:02d}.jpg", f"slide {i}"), "image", i) for i in range(1, 4)]
        meta = PostMeta("instagram", target.url, author="examplecreator", caption="Five tips", date="2026-10-09")
        result = FetchResult(items, meta, "fake")
        if "PARTIAL" in target.url:  # the download stopped after these three items
            result.incomplete = "rate_limited"
        return result

    monkeypatch.setattr(jobs_module, "fetch", _fetch)
    return calls


@pytest.fixture
def client(settings, fake_fetch):
    with TestClient(create_app(settings), base_url="https://testserver") as c:
        yield c


@pytest.fixture
def authed(client):
    client.headers["Authorization"] = f"Bearer {TOKEN}"
    return client


def wait_done(client, job_id, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"done", "error"}:
            return job
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_unauthenticated_page_redirects_to_login_keeping_share_params(client):
    r = client.get("/share?text=https%3A%2F%2Fwww.instagram.com%2Fp%2Fabc%2F", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/login?next=%2Fshare%3Ftext%3D")


def test_unauthenticated_api_is_401(client):
    assert client.get("/api/jobs").status_code == 401
    assert client.post("/api/jobs", json={"text": POST}).status_code == 401


def test_public_assets_need_no_login(client):
    assert client.get("/manifest.webmanifest").json()["share_target"]["method"] == "GET"
    assert client.get("/sw.js").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/healthz").json() == {"ok": True, "cookies": "missing"}


def test_login_flow_sets_cookie(client):
    bad = client.post("/login", data={"token": "wrong", "next": "/share?text=x"}, follow_redirects=False)
    assert "error=1" in bad.headers["location"]
    good = client.post("/login", data={"token": TOKEN, "next": "/share?text=x"}, follow_redirects=False)
    assert good.status_code == 303 and good.headers["location"] == "/share?text=x"
    assert "sharewerk_session" in good.headers["set-cookie"].lower()
    assert "httponly" in good.headers["set-cookie"].lower()
    assert client.get("/api/jobs").status_code == 200


def test_login_rejects_open_redirect(client):
    r = client.post("/login", data={"token": TOKEN, "next": "//evil.example/"}, follow_redirects=False)
    assert r.headers["location"] == "/"


@pytest.mark.parametrize("value,expected", [
    ("/share?x=1", "/share?x=1"), ("//evil", "/"), ("https://evil", "/"), ("/\\evil", "/"), (None, "/"),
])
def test_safe_next(value, expected):
    assert safe_next(value) == expected


def test_security_headers(authed):
    r = authed.get("/")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_job_lifecycle(authed, fake_fetch):
    r = authed.post("/api/jobs", json={"text": f"Look at this {POST}"})
    assert r.status_code == 200, r.text
    job = wait_done(authed, r.json()["id"])
    assert job["status"] == "done", job
    result = job["result"]
    assert result["meta"]["author"] == "examplecreator"
    assert result["packs"]["full"] == [["post.txt", "01.jpg", "02.jpg", "03.jpg"]]
    assert result["packs"]["compact"] is None
    assert result["packs"]["originals"] == [["original-01.jpg", "original-02.jpg", "original-03.jpg"]]
    assert all("path" not in f for f in result["files"].values())

    text = authed.get(f"/api/jobs/{job['id']}/files/post.txt")
    assert text.status_code == 200
    assert "instagram-DPq1aBcXyZ_.txt" in text.headers["content-disposition"]
    assert "Five tips" in text.text
    img = authed.get(f"/api/jobs/{job['id']}/files/01.jpg")
    assert img.headers["content-type"] == "image/jpeg"


def test_duplicate_submission_reuses_job(authed, fake_fetch):
    a = authed.post("/api/jobs", json={"text": POST}).json()
    b = authed.post("/api/jobs", json={"url": "https://instagram.com/p/DPq1aBcXyZ_/"}).json()
    assert a["id"] == b["id"]
    wait_done(authed, a["id"])
    forced = authed.post("/api/jobs", json={"url": POST, "force": True}).json()
    assert forced["id"] != a["id"]


def test_file_access_is_restricted_to_manifest(authed):
    job = wait_done(authed, authed.post("/api/jobs", json={"text": POST}).json()["id"])
    for name in ("job.json", "..%2Fjob.json", "raw%2F01.jpg", "%2Fetc%2Fpasswd"):
        assert authed.get(f"/api/jobs/{job['id']}/files/{name}").status_code == 404
    assert authed.get("/api/jobs/deadbeef/files/post.txt").status_code == 404


def test_invalid_links_are_rejected(authed):
    r = authed.post("/api/jobs", json={"text": "https://www.instagram.com/examplecreator/"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "unsupported_link"
    r = authed.post("/api/jobs", json={"text": "http://10.0.0.1/admin"})
    assert r.json()["detail"]["code"] == "host_not_allowed"
    r = authed.post("/api/jobs", json={"text": "no link here"})
    assert r.json()["detail"]["code"] == "no_url"


def test_failed_download_reports_code(authed):
    r = authed.post("/api/jobs", json={"url": "https://www.instagram.com/p/FAILS/"})
    job = wait_done(authed, r.json()["id"])
    assert job["status"] == "error" and job["error_code"] == "auth_required"


def test_auth_mode_none(settings, fake_fetch):
    with TestClient(create_app(replace(settings, auth_mode="none"))) as c:
        assert c.get("/api/jobs").status_code == 200
        assert c.get("/", follow_redirects=False).status_code == 200


def test_restart_keeps_finished_jobs(settings, fake_fetch):
    with TestClient(create_app(settings), base_url="https://testserver") as c:
        c.headers["Authorization"] = f"Bearer {TOKEN}"
        job = wait_done(c, c.post("/api/jobs", json={"text": POST}).json()["id"])
    with TestClient(create_app(settings), base_url="https://testserver") as c:
        c.headers["Authorization"] = f"Bearer {TOKEN}"
        again = c.get(f"/api/jobs/{job['id']}").json()
        assert again["status"] == "done"
        assert c.get(f"/api/jobs/{job['id']}/files/01.jpg").status_code == 200


def test_login_page_follows_browser_language(client):
    de = client.get("/login", headers={"Accept-Language": "de-DE,de;q=0.9"})
    assert 'lang="de"' in de.text and "Gerät anmelden" in de.text
    en = client.get("/login?error=1", headers={"Accept-Language": "en-US"})
    assert "Sign in device" in en.text and 'aria-invalid="true"' in en.text
    assert "{{" not in de.text and "{{" not in en.text


def test_config_exposes_version_and_retention(authed):
    data = authed.get("/api/config").json()
    assert data["version"] and data["retention_hours"] == 24


def test_manifest_describes_each_picture(authed):
    job = wait_done(authed, authed.post("/api/jobs", json={"text": POST}).json()["id"])
    pic = job["result"]["files"]["02.jpg"]
    assert (pic["number"], pic["kind"], pic["item"], pic["time"]) == (2, "image", 2, None)
    assert job["result"]["incomplete"] == ""


def test_an_incomplete_pack_says_so_in_the_result_and_the_text(authed):
    job = wait_done(authed, authed.post("/api/jobs", json={"url": "https://www.instagram.com/p/PARTIAL/"}).json()["id"])
    assert job["status"] == "done"
    assert job["result"]["incomplete"] == "rate_limited"
    text = authed.get(f"/api/jobs/{job['id']}/files/post.txt").text
    assert "Incomplete:" in text and "rate_limited" in text
