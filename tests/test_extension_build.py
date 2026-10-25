# SPDX-License-Identifier: Apache-2.0
"""tools/build-extension.py: the browser extension as Chrome loads it and as a release ships it."""

import importlib.util
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from app import __version__

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "build-extension.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("build_extension", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> tuple[Path, Path]:
    out = tmp_path_factory.mktemp("dist")
    subprocess.run([sys.executable, str(SCRIPT), str(out)], check=True, capture_output=True, timeout=60)
    name = f"sharewerk-extension-{__version__}"
    return out / name, out / f"{name}.zip"


def test_the_manifest_carries_the_version_of_the_app(built):
    folder, _ = built
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == __version__
    assert "version_name" not in manifest


def test_a_pre_release_keeps_a_version_chrome_accepts():
    tool = load_tool()
    data = tool.manifest(ROOT / "extension" / "manifest.json", "0.2.0-rc.1")
    assert (data["version"], data["version_name"]) == ("0.2.0", "0.2.0-rc.1")


def test_the_design_system_and_the_shared_scripts_are_unchanged_copies(built):
    folder, _ = built
    source = ROOT / "app" / "static" / "azentrius"
    for path in source.rglob("*"):
        if path.is_file():
            assert (folder / "azentrius" / path.relative_to(source)).read_bytes() == path.read_bytes()
    for name in ("theme.js", "icons.js"):
        assert (folder / name).read_bytes() == (ROOT / "app" / "static" / name).read_bytes()
    for name in ("LICENSE", "NOTICE"):
        assert (folder / name).is_file()


def test_every_file_the_extension_refers_to_is_there(built):
    folder, _ = built
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    referred = [manifest["background"]["service_worker"], manifest["action"]["default_popup"],
                manifest["options_ui"]["page"], *manifest["icons"].values(), *manifest["action"]["default_icon"].values()]
    for page in ("popup.html", "options.html"):
        html = (folder / page).read_text(encoding="utf-8")
        refs = re.findall(r'(?:src|href)="([^"#]+)"', html)
        local = [r for r in refs if not r.startswith("https://")]
        # Pages load nothing from the network; the only outside links are plain <a href>.
        assert all(re.search(rf'<a [^>]*href="{re.escape(r)}"', html) for r in refs if r.startswith("https://"))
        referred += local
    for script in folder.glob("*.js"):
        referred += [m + ("" if m.endswith(".js") else ".js") for m in re.findall(r'from "\./([^"]+)"', script.read_text(encoding="utf-8"))]
    missing = sorted({r for r in referred if not (folder / r).is_file()})
    assert missing == []
    for locale in ("en", "de"):
        messages = json.loads((folder / "_locales" / locale / "messages.json").read_text(encoding="utf-8"))
        assert {"name", "description"} <= messages.keys()


def test_the_zip_holds_the_folder_and_is_reproducible(built, tmp_path):
    folder, archive = built
    files = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    with zipfile.ZipFile(archive) as zf:
        assert sorted(zf.namelist()) == files
        assert zf.read("manifest.json") == (folder / "manifest.json").read_bytes()
    subprocess.run([sys.executable, str(SCRIPT), str(tmp_path)], check=True, capture_output=True, timeout=60)
    assert (tmp_path / archive.name).read_bytes() == archive.read_bytes()
