# SPDX-License-Identifier: Apache-2.0
"""HTML pages whose script and stylesheet URLs carry a hash of the file's content.

The service worker answers /static/ requests from its cache first (stale-while-revalidate),
keyed by the full URL. A page that asks for `/static/app.js?v=<hash>` therefore always gets the
file it was written for, even from the service worker of an older version: a changed file has
a new URL, which that worker never cached, so the request goes to the network. The release
version cannot serve as the key, because it stays the same between feature merges.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

STATIC = Path(__file__).parent / "static"
ASSET_URL = re.compile(r'(\b(?:src|href)=")/static/([^"?#]+)(")')


@lru_cache(maxsize=None)
def version(name: str) -> str:
    """First 12 hex digits of the SHA-256 of a file in static/ (the files never change at run time)."""
    return hashlib.sha256((STATIC / name).read_bytes()).hexdigest()[:12]


def page(name: str) -> str:
    """A page from static/ with ?v=<hash> on every /static/ URL that names an existing file."""
    html = (STATIC / name).read_text(encoding="utf-8")

    def versioned(m: re.Match) -> str:
        asset = m.group(2)
        if ".." in asset.split("/") or not (STATIC / asset).is_file():
            return m.group(0)
        return f"{m.group(1)}/static/{asset}?v={version(asset)}{m.group(3)}"

    return ASSET_URL.sub(versioned, html)
