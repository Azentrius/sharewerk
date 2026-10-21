# SPDX-License-Identifier: Apache-2.0
"""Pages refer to their scripts and stylesheets by content hash (see app/assets.py)."""

import hashlib
import re
from dataclasses import replace

from fastapi.testclient import TestClient

from app.assets import STATIC, page
from app.main import create_app


def urls(html: str) -> list[str]:
    return re.findall(r'(?:src|href)="(/static/[^"]+)"', html)


def test_every_static_url_carries_the_hash_of_its_file(settings):
    with TestClient(create_app(replace(settings, auth_mode="none"))) as client:
        index = client.get("/")
        login = page("login.html")
    assert index.headers["cache-control"] == "no-cache"
    for found in urls(index.text) + urls(login):
        path, _, version = found.partition("?v=")
        content = (STATIC / path.removeprefix("/static/")).read_bytes()
        assert version == hashlib.sha256(content).hexdigest()[:12], found
    assert any("app.js?v=" in u for u in urls(index.text))
    assert any("icons.js?v=" in u for u in urls(index.text))


def test_a_changed_file_gets_a_new_url(tmp_path, monkeypatch):
    from app import assets

    (tmp_path / "x.js").write_text("one", encoding="utf-8")
    (tmp_path / "p.html").write_text('<script src="/static/x.js"></script><a href="/static/gone.js">', encoding="utf-8")
    monkeypatch.setattr(assets, "STATIC", tmp_path)
    assets.version.cache_clear()
    first = assets.page("p.html")
    (tmp_path / "x.js").write_text("two", encoding="utf-8")
    assets.version.cache_clear()
    second = assets.page("p.html")
    assets.version.cache_clear()
    assert first != second and "x.js?v=" in second
    assert 'href="/static/gone.js"' in second  # a missing file keeps its plain URL
