# SPDX-License-Identifier: Apache-2.0
"""Download a post's media with gallery-dl and/or yt-dlp.

Both tools are called as subprocesses with argument lists (never a shell), so
nothing from the shared URL can be interpreted as a command.

Instagram: gallery-dl first (it handles image carousels), yt-dlp as fallback.
Facebook:  yt-dlp first (videos and reels), gallery-dl as fallback (photos).
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .urls import Target

log = logging.getLogger(__name__)

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".avif", ".gif"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".mkv", ".m4v"}
DOWNLOAD_TIMEOUT = 300


class FetchError(RuntimeError):
    """Download failed. `code` is a stable identifier the UI translates."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


@dataclass
class MediaItem:
    path: Path
    kind: str  # "image" | "video"
    index: int  # 1-based position in the post


@dataclass
class PostMeta:
    platform: str
    url: str
    author: str = ""
    author_name: str = ""
    caption: str = ""
    date: str = ""  # ISO date (YYYY-MM-DD) if known
    title: str = ""


@dataclass
class FetchResult:
    items: list[MediaItem]
    meta: PostMeta
    tool: str
    notes: list[str] = field(default_factory=list)


def classify_error(output: str) -> str:
    text = output.lower()
    if any(s in text for s in ("unable to connect", "proxyerror", "name or service not known",
                               "temporary failure in name resolution", "connection refused",
                               "network is unreachable")):
        return "unreachable"
    if any(s in text for s in ("401", "login required", "log in", "cookies", "checkpoint", "redirect to login")):
        return "auth_required"
    if any(s in text for s in ("429", "rate limit", "rate-limit", "too many requests", "please wait")):
        return "rate_limited"
    if any(s in text for s in ("404", "not available", "does not exist", "not found", "unavailable", "private")):
        return "not_found"
    if any(s in text for s in ("unsupported url", "no suitable extractor", "no video formats")):
        return "unsupported"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    return "download_failed"


def _tool(name: str) -> list[str]:
    """Prefer the console script next to the interpreter, fall back to `python -m`."""
    candidate = Path(sys.executable).with_name(name)
    if candidate.exists():
        return [str(candidate)]
    found = shutil.which(name)
    if found:
        return [found]
    module = name.replace("-", "_")
    return [sys.executable, "-m", module]


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    safe = [("<cookies>" if prev == "--cookies" else c) for prev, c in zip([""] + cmd, cmd)]
    log.info("running: %s", " ".join(safe))
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=DOWNLOAD_TIMEOUT,
        check=False,
    )


def _media_files(directory: Path) -> list[Path]:
    return sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXT | VIDEO_EXT and not p.name.endswith(".part")
    )


def _check(tool: str, proc: subprocess.CompletedProcess[str], files: list[Path]) -> None:
    """Raise FetchError unless the tool finished cleanly with at least one file.

    A non-zero exit status after some files means items of the post are missing, so it is a
    failure too (and the caller tries the other tool). The configured limits (--range,
    --playlist-items, the maximum file size) end with status 0 in both tools.
    """
    if proc.returncode == 0 and files:
        return
    output = proc.stderr + proc.stdout
    detail = _tail(output)
    if proc.returncode != 0:
        detail = f"{tool} ended with exit status {proc.returncode} after {len(files)} file(s)\n{detail}"
    raise FetchError(classify_error(output), detail.strip())


def _kind(path: Path) -> str:
    return "video" if path.suffix.lower() in VIDEO_EXT else "image"


def _iso_date(value: object) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).date().isoformat()
    text = str(value)
    if len(text) == 8 and text.isdigit():  # yt-dlp upload_date YYYYMMDD
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10]


def _first(data: dict, *keys: str) -> str:
    for key in keys:
        cur: object = data
        for part in key.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if cur not in (None, ""):
            return str(cur)
    return ""


# --------------------------------------------------------------------- gallery-dl

def run_gallery_dl(target: Target, raw: Path, cookies: Path | None, settings: Settings) -> FetchResult:
    # The tool runs inside raw, so every path it gets must be absolute.
    raw = raw.resolve()
    config = settings.gallery_dl_config.resolve()
    cmd = _tool("gallery-dl") + [
        "--directory", str(raw),
        "--write-metadata",
        "--range", f"1-{settings.max_items}",
        "--filesize-max", f"{settings.max_download_mb}M",
        "--no-part",
    ]
    if config.is_file():
        cmd += ["--config", str(config)]
    if cookies:
        cmd += ["--cookies", str(cookies.resolve())]
    cmd.append(target.url)

    proc = _run(cmd, cwd=raw)
    files = _media_files(raw)
    _check("gallery-dl", proc, files)

    entries = []
    for path in files:
        meta_path = path.with_name(path.name + ".json")
        data: dict = {}
        if meta_path.is_file():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
        num = data.get("num")
        entries.append((int(num) if isinstance(num, int) else 10_000, path.name, path, data))
    entries.sort(key=lambda e: (e[0], e[1]))

    first = entries[0][3]
    meta = PostMeta(
        platform=target.platform,
        url=target.url,
        author=_first(first, "username", "owner.username", "user.name", "author"),
        author_name=_first(first, "fullname", "owner.full_name", "user.full_name"),
        caption=_first(first, "description", "caption", "content", "message"),
        date=_iso_date(_first(first, "date", "post_date", "timestamp")),
        title=_first(first, "title"),
    )
    items = [MediaItem(path, _kind(path), i + 1) for i, (_, _, path, _) in enumerate(entries)]
    return FetchResult(items, meta, "gallery-dl")


# ------------------------------------------------------------------------- yt-dlp

def run_yt_dlp(target: Target, raw: Path, cookies: Path | None, settings: Settings) -> FetchResult:
    # The tool runs inside raw, so every path it gets must be absolute.
    raw = raw.resolve()
    cmd = _tool("yt-dlp") + [
        "--use-extractors", "instagram.*,facebook.*",
        "--output", str(raw / "%(playlist_index&{:03d}_|)s%(id)s.%(ext)s"),
        "--write-info-json",
        "--no-write-playlist-metafiles",
        "--playlist-items", f"1:{settings.max_items}",
        "--max-filesize", f"{settings.max_download_mb}M",
        "--format", "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
        "--merge-output-format", "mp4",
        "--restrict-filenames",
        "--no-progress",
        "--no-mtime",
        "--socket-timeout", "20",
        "--retries", "2",
    ]
    if cookies:
        cmd += ["--cookies", str(cookies.resolve())]
    cmd.append(target.url)

    proc = _run(cmd, cwd=raw)
    files = _media_files(raw)
    _check("yt-dlp", proc, files)

    infos: dict[str, dict] = {}
    for info_path in raw.glob("*.info.json"):
        try:
            infos[info_path.name[: -len(".info.json")]] = json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    first = next((infos[p.stem] for p in files if p.stem in infos), {})
    meta = PostMeta(
        platform=target.platform,
        url=target.url,
        author=_first(first, "uploader_id", "channel", "uploader"),
        author_name=_first(first, "uploader", "channel"),
        caption=_first(first, "description"),
        date=_iso_date(first.get("upload_date") or first.get("timestamp")),
        title=_first(first, "title"),
    )
    if meta.author_name == meta.author:
        meta.author_name = ""
    items = [MediaItem(path, _kind(path), i + 1) for i, path in enumerate(files)]
    return FetchResult(items, meta, "yt-dlp")


# ------------------------------------------------------------------------ public

def _tail(text: str, lines: int = 6) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def fetch(target: Target, workdir: Path, settings: Settings) -> FetchResult:
    """Download into workdir/raw. Cookies are copied per job and deleted after,
    because both tools write updated cookies back into the file they were given."""
    workdir = workdir.resolve()  # the tools run in raw; relative paths would point below it
    raw = workdir / "raw"
    raw.mkdir(parents=True, exist_ok=True)

    cookies: Path | None = None
    if settings.cookies_file.is_file():
        cookies = workdir / "cookies.txt"
        shutil.copyfile(settings.cookies_file, cookies)
        cookies.chmod(0o600)

    order = (
        [run_gallery_dl, run_yt_dlp]
        if target.platform == "instagram"
        else [run_yt_dlp, run_gallery_dl]
    )
    errors: list[FetchError] = []
    try:
        for runner in order:
            for leftover in raw.iterdir():
                if leftover.is_file():
                    leftover.unlink()
            try:
                result = runner(target, raw, cookies, settings)
                if errors:
                    result.notes.append(f"first tool failed: {errors[0].code}")
                return result
            except FetchError as exc:
                log.warning("%s failed for %s: %s", runner.__name__, target.url, exc.detail)
                errors.append(exc)
            except subprocess.TimeoutExpired:
                errors.append(FetchError("timeout", f"{runner.__name__} timed out"))
    finally:
        if cookies and cookies.exists():
            cookies.unlink()

    # Prefer the most telling error: an auth problem explains most other failures.
    codes = [e.code for e in errors]
    for preferred in ("auth_required", "rate_limited", "not_found", "timeout"):
        if preferred in codes:
            err = errors[codes.index(preferred)]
            break
    else:
        err = errors[0]
    if cookies is None and err.code in {"download_failed", "not_found", "unsupported"} and target.platform == "instagram":
        err = FetchError("auth_required", err.detail)
    raise err
