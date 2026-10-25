#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the browser extension: extension/ plus the files it shares with the app, with the
version of app/__init__.py.

Usage: python tools/build-extension.py [OUT_DIR]   (default: dist)

Writes OUT_DIR/sharewerk-extension-VERSION/ (in Chrome: chrome://extensions, developer mode,
"Load unpacked") and OUT_DIR/sharewerk-extension-VERSION.zip with the same files, for a release.
The zip is reproducible: same sources, same bytes. Standard library only.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Copied unchanged from the app, so each has one source: the design system copies, the theme
# switch, the icons, and the license texts the fonts and icons require.
SHARED = {
    "app/static/azentrius": "azentrius",
    "app/static/theme.js": "theme.js",
    "app/static/icons.js": "icons.js",
    "LICENSE": "LICENSE",
    "NOTICE": "NOTICE",
    "LICENSES": "LICENSES",
}
# package.json only tells Node (tests, node --check) that the scripts are ES modules.
SKIP = {"__pycache__", ".DS_Store", "Thumbs.db", "package.json"}


def version() -> str:
    text = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "([^"]+)"$', text, re.MULTILINE)
    if not match:
        raise SystemExit("no __version__ in app/__init__.py")
    return match.group(1)


def manifest(source: Path, release: str) -> dict:
    """The manifest with the version. Chrome takes one to four numbers only; a pre-release such
    as 0.2.0-rc.1 becomes version 0.2.0 with the full name as version_name."""
    data = json.loads(source.read_text(encoding="utf-8"))
    numbers = release.split("-", 1)[0]
    if not re.fullmatch(r"\d+(\.\d+){0,3}", numbers):
        raise SystemExit(f"version {release} does not fit a Chrome extension")
    out = {}
    for key, value in data.items():
        out[key] = value
        if key == "name":  # keep the version next to the name, where people look for it
            out["version"] = numbers
            if numbers != release:
                out["version_name"] = release
    return out


def copy(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, target, ignore=shutil.ignore_patterns(*SKIP))
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def build(out: Path) -> tuple[Path, Path]:
    release = version()
    name = f"sharewerk-extension-{release}"
    target = out / name
    shutil.rmtree(target, ignore_errors=True)
    copy(ROOT / "extension", target)
    for source, dest in SHARED.items():
        if (target / dest).exists():
            raise SystemExit(f"extension/{dest} would be overwritten by {source}")
        copy(ROOT / source, target / dest)
    data = manifest(ROOT / "extension" / "manifest.json", release)
    (target / "manifest.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    archive = out / f"{name}.zip"
    files = sorted(p for p in target.rglob("*") if p.is_file())
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(target).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())
    return target, archive


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist"
    out.mkdir(parents=True, exist_ok=True)
    folder, archive = build(out.resolve())
    print(folder)
    print(archive)


if __name__ == "__main__":
    main()
