# SPDX-License-Identifier: Apache-2.0
"""fetch.py against a real subprocess that stands in for gallery-dl and yt-dlp (fake_downloader.py)."""

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from app import fetch as fetch_module
from app.config import load_settings
from app.fetch import FetchError, fetch, run_gallery_dl, run_yt_dlp
from app.urls import Target

FAKE = Path(__file__).with_name("fake_downloader.py")
INSTAGRAM = Target("https://www.instagram.com/p/DPq1aBcXyZ_/", "instagram", "post", "DPq1aBcXyZ_")
FACEBOOK = Target("https://www.facebook.com/reel/954162721072206/", "facebook", "reel", "954162721072206")
RUNNERS = [(run_gallery_dl, "gallery-dl"), (run_yt_dlp, "yt-dlp")]


class FakeTools:
    def __init__(self, monkeypatch, log: Path):
        self.monkeypatch = monkeypatch
        self.log = log

    def set(self, tool: str, files: int = 0, exit: int = 0, stderr: str = "") -> None:
        prefix = "FAKE_" + tool.upper().replace("-", "_") + "_"
        self.monkeypatch.setenv(prefix + "FILES", str(files))
        self.monkeypatch.setenv(prefix + "EXIT", str(exit))
        self.monkeypatch.setenv(prefix + "STDERR", stderr)

    def calls(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def tools(monkeypatch, tmp_path) -> FakeTools:
    monkeypatch.setattr(fetch_module, "_tool", lambda name: [sys.executable, str(FAKE), name])
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "calls.jsonl"))
    fake = FakeTools(monkeypatch, tmp_path / "calls.jsonl")
    for tool in ("gallery-dl", "yt-dlp"):
        fake.set(tool)
    return fake


@pytest.fixture
def raw(tmp_path) -> Path:
    path = tmp_path / "job" / "raw"
    path.mkdir(parents=True)
    return path


@pytest.fixture
def with_cookies(settings, tmp_path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    return replace(settings, cookies_file=cookies)


# ------------------------------------------------------------------ exit status

@pytest.mark.parametrize("runner,tool", RUNNERS)
def test_media_file_with_error_exit_is_a_failure(runner, tool, tools, raw, settings):
    tools.set(tool, files=1, exit=1, stderr="ERROR: item 2: HTTP Error 500: Internal Server Error\n")
    with pytest.raises(FetchError) as exc:
        runner(INSTAGRAM, raw, None, settings)
    assert exc.value.code == "download_failed"
    assert "exit status 1" in exc.value.detail and "HTTP Error 500" in exc.value.detail


@pytest.mark.parametrize("runner,tool", RUNNERS)
def test_complete_download_succeeds(runner, tool, tools, raw, settings):
    tools.set(tool, files=2)
    result = runner(INSTAGRAM, raw, None, settings)
    assert result.tool == tool
    assert [item.index for item in result.items] == [1, 2]
    assert all(item.path.parent == raw for item in result.items)
    assert result.meta.author == "examplecreator"


@pytest.mark.parametrize("runner,tool", RUNNERS)
def test_error_without_files_is_classified(runner, tool, tools, raw, settings):
    tools.set(tool, exit=1, stderr="ERROR: HTTP Error 429: Too Many Requests\n")
    with pytest.raises(FetchError) as exc:
        runner(INSTAGRAM, raw, None, settings)
    assert exc.value.code == "rate_limited"


@pytest.mark.parametrize("runner,tool", RUNNERS)
def test_configured_limits_are_not_failures(runner, tool, tools, raw, settings):
    # The post has 5 items, max_items keeps 2, and the tool skipped an oversized file. Both tools
    # end with status 0 then, and the result is complete as far as the settings allow.
    tools.set(tool, files=5, stderr="[download] File is larger than max-filesize. Aborting.\n")
    result = runner(INSTAGRAM, raw, None, replace(settings, max_items=2))
    assert len(result.items) == 2


# --------------------------------------------------------------------- fallback

def test_partial_first_tool_falls_back_to_the_second(tools, tmp_path, with_cookies):
    tools.set("gallery-dl", files=1, exit=4, stderr="[instagram][error] HttpError: 500 for item 2\n")
    tools.set("yt-dlp", files=2)
    result = fetch(INSTAGRAM, tmp_path / "job", with_cookies)
    assert result.tool == "yt-dlp"
    assert len(result.items) == 2
    assert result.notes == ["first tool failed: download_failed"]
    # Nothing of the partial first attempt is left over in the pack's source folder.
    assert [p.name for p in (tmp_path / "job" / "raw").iterdir() if p.suffix == ".jpg"] == []


def test_partial_downloads_of_both_tools_end_in_an_error(tools, tmp_path, settings):
    tools.set("yt-dlp", files=1, exit=1, stderr="ERROR: [facebook] clip2: Unable to extract video data\n")
    tools.set("gallery-dl", files=1, exit=4, stderr="[facebook][error] HttpError: 500\n")
    with pytest.raises(FetchError) as exc:
        fetch(FACEBOOK, tmp_path / "job", settings)
    assert exc.value.code == "download_failed"
    assert [c["tool"] for c in tools.calls()] == ["yt-dlp", "gallery-dl"]


def test_complete_first_tool_needs_no_fallback(tools, tmp_path, with_cookies):
    tools.set("gallery-dl", files=3)
    result = fetch(INSTAGRAM, tmp_path / "job", with_cookies)
    assert (result.tool, len(result.items), result.notes) == ("gallery-dl", 3, [])
    assert [c["tool"] for c in tools.calls()] == ["gallery-dl"]


# ------------------------------------------------------------------------ paths

@pytest.mark.parametrize("target,tool", [(INSTAGRAM, "gallery-dl"), (FACEBOOK, "yt-dlp")])
def test_relative_paths_reach_the_tool_resolved(target, tool, tools, tmp_path, settings, monkeypatch):
    # The documented development start uses SHAREWERK_DATA_DIR=./data; cookies and the
    # gallery-dl config may be relative as well. The tools run with the job's raw folder as
    # working directory, so every path has to be resolved before that.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "cookies.txt").write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    (tmp_path / "secrets" / "gallery-dl.conf").write_text("{}", encoding="utf-8")
    relative = replace(
        settings,
        data_dir=Path("data"),
        cookies_file=Path("secrets/cookies.txt"),
        gallery_dl_config=Path("secrets/gallery-dl.conf"),
    )
    tools.set(tool, files=1)

    result = fetch(target, relative.jobs_dir / "job1", relative)

    raw = tmp_path / "data" / "jobs" / "job1" / "raw"
    media = sorted(p.resolve() for p in raw.iterdir() if p.suffix in {".jpg", ".mp4"})
    assert len(media) == 1
    assert [item.path.resolve() for item in result.items] == media
    assert not (raw / "data").exists()
    call = tools.calls()[0]
    assert Path(call["cwd"]).resolve() == raw.resolve()
    assert call["cookies_found"] is True
    if tool == "gallery-dl":
        assert call["config_found"] is True


def test_absolute_paths_keep_working(tools, tmp_path, with_cookies):
    config = tmp_path / "gallery-dl.conf"
    config.write_text("{}", encoding="utf-8")
    tools.set("gallery-dl", files=1)
    result = fetch(INSTAGRAM, tmp_path / "job", replace(with_cookies, gallery_dl_config=config))
    assert result.items[0].path.resolve().parent == (tmp_path / "job" / "raw").resolve()
    call = tools.calls()[0]
    assert call["cookies_found"] is True and call["config_found"] is True


def test_settings_resolve_relative_paths_at_load(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHAREWERK_AUTH_MODE", "none")
    monkeypatch.setenv("SHAREWERK_DATA_DIR", "./data")
    monkeypatch.setenv("SHAREWERK_COOKIES_FILE", "secrets/cookies.txt")
    monkeypatch.setenv("SHAREWERK_GALLERY_DL_CONFIG", str(tmp_path / "abs" / "gallery-dl.conf"))
    s = load_settings()
    assert s.data_dir == (tmp_path / "data").resolve()
    assert s.cookies_file == (tmp_path / "secrets" / "cookies.txt").resolve()
    assert s.gallery_dl_config == (tmp_path / "abs" / "gallery-dl.conf").resolve()
    assert s.data_dir.is_absolute() and s.jobs_dir.is_absolute() and s.models_dir.is_absolute()
