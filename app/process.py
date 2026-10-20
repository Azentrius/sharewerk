# SPDX-License-Identifier: Apache-2.0
"""Turn downloaded media into a share-ready pack.

For every post item:
  image -> resized JPEG (long edge SHAREWERK_IMAGE_MAX_EDGE, default 1568 px,
           sharp enough for small text, small enough to share quickly)
  video -> a handful of key frames (scene changes plus even spacing)
           and a transcript of the audio track

Then a plain-text file with source, author, caption, image list and
transcripts is written. Android's share sheet accepts at most 10 files per
share, so when there are more pictures, "contact sheets" are built that
combine 2 or 4 pictures each, so the whole post still fits into one share.
"""

from __future__ import annotations

import json
import logging
import math
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .config import Settings
from .fetch import FetchResult, MediaItem
from .transcribe import Transcript, transcribe

log = logging.getLogger(__name__)

MAX_SHARE_FILES = 10  # Chrome's limit for navigator.share({files})

# Contact sheets are images without a theme, so they use the base theme
# "Azentrius hell" of the Azentrius Design System. The number badge looks like
# a neutral label: tint-neutral with on-tint-neutral, plus a ring in
# line-control so it stays visible on light and on dark pictures.
SHEET_BG = (0xF2, 0xF1, 0xEE)      # bg-page
BADGE_BG = (0xE7, 0xE4, 0xDD)      # tint-neutral
BADGE_TEXT = (0x0A, 0x0A, 0x0F)    # on-tint-neutral
BADGE_RING = (0x8A, 0x86, 0x7C)    # line-control
BADGE_FONT = Path(__file__).parent / "static" / "azentrius" / "fonts" / "DMSans-VF.woff2"
MAX_VISUALS = 36  # 9 sheets x 4 tiles
JPEG_QUALITY = 85
SHOWINFO_RE = re.compile(r"pts_time:([0-9.]+)")


@dataclass
class Visual:
    file: str
    item: int
    kind: str  # "image" | "frame"
    time: float | None = None

    def label(self) -> str:
        if self.kind == "frame" and self.time is not None:
            return f"item {self.item} (video), frame at {fmt_time(self.time)}"
        return f"item {self.item} (image)"


@dataclass
class VideoInfo:
    item: int
    duration: float
    truncated: bool
    transcript: Transcript | None
    has_audio: bool


@dataclass
class Pack:
    visuals: list[Visual] = field(default_factory=list)
    sheets: list[tuple[str, list[int]]] = field(default_factory=list)  # (file, visual numbers)
    videos: list[VideoInfo] = field(default_factory=list)
    text_full: str = ""
    text_compact: str = ""


def fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))  # truncated, like video players; app.js does the same
    return f"{seconds // 60}:{seconds % 60:02d}"


# ------------------------------------------------------------------------ ffmpeg

def probe(path: Path) -> tuple[float, bool]:
    """Return (duration in seconds, has audio track)."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, timeout=60, check=False,
    )
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        data = {}
    duration = float(data.get("format", {}).get("duration") or 0.0)
    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    return duration, has_audio


def scene_changes(path: Path, limit_seconds: float, threshold: float = 0.3) -> list[float]:
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-t", f"{limit_seconds:.2f}", "-i", str(path),
            "-an", "-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-",
        ],
        capture_output=True, text=True, timeout=600, check=False,
    )
    return [float(m) for m in SHOWINFO_RE.findall(proc.stderr)]


def pick_times(duration: float, scenes: list[float], count: int) -> list[float]:
    """Choose `count` timestamps: the opening, scene changes, then even spacing."""
    if duration <= 0 or count <= 0:
        return []
    count = min(count, max(1, int(duration)))
    candidates = [min(0.5, duration / 2)] + [t for t in scenes if 0 < t < duration - 0.2]
    if len(candidates) < count:
        candidates += [duration * (i + 0.5) / count for i in range(count)]
    min_gap = max(1.0, duration / (count * 3))
    kept: list[float] = []
    for t in sorted(candidates):
        if not kept or t - kept[-1] >= min_gap:
            kept.append(t)
    if len(kept) > count:
        if count == 1:
            return [kept[0]]
        kept = [kept[round(i * (len(kept) - 1) / (count - 1))] for i in range(count)]
    return kept


def frame_count(duration: float, max_frames: int) -> int:
    if duration < 2:
        return 1
    return max(2, min(max_frames, math.ceil(duration / 6)))


def extract_frame(video: Path, t: float, dest: Path) -> bool:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video),
         "-frames:v", "1", "-q:v", "2", str(dest)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    return proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0


def extract_audio(video: Path, dest: Path, limit_seconds: float) -> bool:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-t", f"{limit_seconds:.2f}",
         "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(dest)],
        capture_output=True, text=True, timeout=600, check=False,
    )
    return proc.returncode == 0 and dest.is_file()


# ------------------------------------------------------------------------ images

def save_jpeg(src: Path, dest: Path, max_edge: int) -> bool:
    try:
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)
            if getattr(img, "is_animated", False):
                img.seek(0)
            img = img.convert("RGB")
            img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            img.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        return True
    except (OSError, ValueError) as exc:
        log.warning("could not convert %s: %s", src.name, exc)
        return False


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """DM Sans 600 from the design system's font file, Pillow's own font as fallback."""
    try:
        font = ImageFont.truetype(str(BADGE_FONT), size)
        try:
            font.set_variation_by_axes([600])
        except (OSError, ValueError):
            pass
        return font
    except OSError:
        try:
            return ImageFont.load_default(size=size)
        except TypeError:  # very old Pillow
            return ImageFont.load_default()


def build_sheet(paths: list[Path], numbers: list[int], dest: Path, max_edge: int) -> None:
    """Combine 2 or 4 images into one picture, each tile badged with its number."""
    images = [Image.open(p).convert("RGB") for p in paths]
    try:
        n = len(images)
        cols = 2 if n > 1 else 1
        rows = math.ceil(n / cols)
        aspect = sorted(i.width / i.height for i in images)[n // 2]  # median width/height
        gap = 8
        # Size the grid so its longer side equals max_edge.
        unit_w, unit_h = aspect, 1.0
        grid_w, grid_h = cols * unit_w, rows * unit_h
        scale = (max_edge - gap * (max(cols, rows) + 1)) / max(grid_w, grid_h)
        cell_w, cell_h = int(unit_w * scale), int(unit_h * scale)
        sheet_w = cols * cell_w + gap * (cols + 1)
        sheet_h = rows * cell_h + gap * (rows + 1)
        sheet = Image.new("RGB", (sheet_w, sheet_h), SHEET_BG)
        draw = ImageDraw.Draw(sheet)
        badge = max(28, cell_w // 9)
        ring = max(2, badge // 14)
        font = _font(int(badge * 0.58))
        for idx, (img, number) in enumerate(zip(images, numbers)):
            tile = ImageOps.contain(img, (cell_w, cell_h), Image.Resampling.LANCZOS)
            col, row = idx % cols, idx // cols
            x0 = gap + col * (cell_w + gap)
            y0 = gap + row * (cell_h + gap)
            ox = x0 + (cell_w - tile.width) // 2
            oy = y0 + (cell_h - tile.height) // 2
            sheet.paste(tile, (ox, oy))
            # Number badge as a pill, like a neutral label.
            text = str(number)
            text_w = draw.textlength(text, font=font)
            badge_w = max(badge, int(text_w + badge * 0.7))
            bx, by = ox + 8, oy + 8
            draw.rounded_rectangle((bx, by, bx + badge_w, by + badge), radius=badge // 2,
                                   fill=BADGE_BG, outline=BADGE_RING, width=ring)
            draw.text((bx + badge_w / 2, by + badge / 2), text, fill=BADGE_TEXT, font=font, anchor="mm")
        sheet.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    finally:
        for img in images:
            img.close()


def tiles_per_sheet(n_visuals: int) -> int:
    """Smallest tile count (1, 2 or 4) so that all visuals fit beside the text file."""
    slots = MAX_SHARE_FILES - 1
    for per_sheet in (1, 2, 4):
        if math.ceil(n_visuals / per_sheet) <= slots:
            return per_sheet
    return 4


# --------------------------------------------------------------------- pipeline

def build_pack(
    result: FetchResult, workdir: Path, settings: Settings,
    on_stage=lambda stage: None, on_progress=lambda fraction: None,
) -> Pack:
    """on_progress gets the share of the transcription done over all videos (0 to 1)."""
    out = workdir / "out"
    tmp = workdir / "tmp"
    out.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)

    pack = Pack()
    images = [i for i in result.items if i.kind == "image"]
    videos = [i for i in result.items if i.kind == "video"]
    frame_budget = max(0, MAX_VISUALS - len(images))
    per_video_cap = settings.max_frames
    if videos:
        per_video_cap = max(1, min(settings.max_frames, frame_budget // len(videos)))

    probed: dict[int, tuple[float, bool]] = {v.index: probe(v.path) for v in videos}

    on_stage("processing")
    counter = 0
    for item in result.items:
        if item.kind == "image":
            counter += 1
            name = f"{counter:02d}.jpg"
            if save_jpeg(item.path, out / name, settings.image_max_edge):
                pack.visuals.append(Visual(name, item.index, "image"))
            else:
                counter -= 1
            continue

        duration, _ = probed[item.index]
        limit = min(duration, float(settings.max_video_seconds)) if duration else float(settings.max_video_seconds)
        count = min(per_video_cap, frame_count(limit, settings.max_frames))
        scenes = scene_changes(item.path, limit) if count > 1 else []
        for t in pick_times(limit, scenes, count):
            raw_frame = tmp / f"frame-{item.index}-{t:.2f}.jpg"
            if not extract_frame(item.path, t, raw_frame):
                continue
            counter += 1
            name = f"{counter:02d}.jpg"
            if save_jpeg(raw_frame, out / name, settings.image_max_edge):
                pack.visuals.append(Visual(name, item.index, "frame", t))
            else:
                counter -= 1

    if any(v.kind == "video" for v in result.items):
        on_stage("transcribing")
    # Progress over all videos, weighted by the length that is transcribed of each.
    lengths = {
        item.index: min(probed[item.index][0] or settings.max_video_seconds, float(settings.max_video_seconds))
        for item in videos if probed[item.index][1]
    }
    total = sum(lengths.values()) or 1.0
    before = 0.0
    for item in videos:
        duration, has_audio = probed[item.index]
        limit = min(duration, float(settings.max_video_seconds)) if duration else float(settings.max_video_seconds)
        transcript = None
        if has_audio and settings.transcription_enabled:
            wav = tmp / f"audio-{item.index}.wav"
            share = lengths[item.index] / total
            if extract_audio(item.path, wav, limit):
                try:
                    # transcribe() runs to the end here, so the closure sees this video's values.
                    transcript = transcribe(wav, settings, lambda f: on_progress(before + f * share))
                except Exception:  # noqa: BLE001 - a broken transcript must not lose the pack
                    log.exception("transcription failed for item %s", item.index)
                finally:
                    wav.unlink(missing_ok=True)
            before += share
        pack.videos.append(VideoInfo(item.index, duration, duration > settings.max_video_seconds, transcript, has_audio))

    per_sheet = tiles_per_sheet(len(pack.visuals))
    if per_sheet > 1:
        for start in range(0, len(pack.visuals), per_sheet):
            group = pack.visuals[start:start + per_sheet]
            numbers = list(range(start + 1, start + 1 + len(group)))
            name = f"sheet-{start // per_sheet + 1:02d}.jpg"
            build_sheet([out / v.file for v in group], numbers, out / name, settings.image_max_edge)
            pack.sheets.append((name, numbers))

    for leftover in tmp.iterdir():
        leftover.unlink(missing_ok=True)

    pack.text_full = render_text(result, pack, compact=False, settings=settings)
    pack.text_compact = render_text(result, pack, compact=True, settings=settings) if pack.sheets else ""
    return pack


# -------------------------------------------------------------------------- text

PLATFORM_NAMES = {"instagram": "Instagram", "facebook": "Facebook"}


def render_text(result: FetchResult, pack: Pack, compact: bool, settings: Settings) -> str:
    meta = result.meta
    lines = [f"Shared post from {PLATFORM_NAMES.get(meta.platform, meta.platform)}", f"Source: {meta.url}"]
    if meta.author or meta.author_name:
        who = f"@{meta.author}" if meta.author else ""
        if meta.author_name:
            who = f"{who} ({meta.author_name})" if who else meta.author_name
        lines.append(f"Author: {who}")
    if meta.date:
        lines.append(f"Posted: {meta.date}")
    n_img = sum(1 for i in result.items if i.kind == "image")
    n_vid = sum(1 for i in result.items if i.kind == "video")
    parts = []
    if n_img:
        parts.append(f"{n_img} image{'s' if n_img != 1 else ''}")
    if n_vid:
        parts.append(f"{n_vid} video{'s' if n_vid != 1 else ''}")
    lines.append(f"Contents: {', '.join(parts) or 'nothing'}")
    if result.incomplete:
        lines.append(
            f"Incomplete: the download stopped early ({result.incomplete}); "
            "the post may have more items than these."
        )
    lines.append("")

    if pack.visuals:
        lines.append("Attached pictures, in order:")
        if compact:
            numbered = {i + 1: v for i, v in enumerate(pack.visuals)}
            for name, numbers in pack.sheets:
                span = f"pictures {numbers[0]}-{numbers[-1]}" if len(numbers) > 1 else f"picture {numbers[0]}"
                lines.append(f"  {name} combines {span} (number badges top left):")
                for n in numbers:
                    lines.append(f"    {n}: {numbered[n].label()}")
        else:
            for v in pack.visuals:
                lines.append(f"  {v.file}: {v.label()}")
        if any(v.kind == "frame" for v in pack.visuals):
            lines.append("  Video frames are stills taken at scene changes; the video itself is not attached.")
        lines.append("")

    if meta.title and meta.title not in meta.caption and not meta.title.lower().startswith(("video by", "post by")):
        lines += ["--- Title ---", meta.title.strip(), ""]
    lines += ["--- Caption ---", meta.caption.strip() or "(no caption)", ""]

    for video in pack.videos:
        head = f"--- Transcript: item {video.item} (video, {fmt_time(video.duration)}) ---"
        lines.append(head)
        if not video.has_audio:
            lines.append("(video has no audio track)")
        elif not settings.transcription_enabled:
            lines.append("(transcription disabled)")
        elif video.transcript is None:
            lines.append("(transcription failed)")
        elif not video.transcript.segments:
            lines.append("(no speech detected; probably music only)")
        else:
            lines.append(f"Language: {video.transcript.language}")
            for start, text in video.transcript.segments:
                lines.append(f"[{fmt_time(start)}] {text}")
        if video.truncated:
            lines.append(f"(only the first {fmt_time(settings.max_video_seconds)} were processed)")
        lines.append("")

    if any(v.transcript and v.transcript.segments for v in pack.videos):
        lines.append("Transcripts were generated automatically and may contain errors.")
    return "\n".join(lines).rstrip() + "\n"


def share_batches(files: list[str], text_name: str) -> list[list[str]]:
    """Split files into share batches of at most MAX_SHARE_FILES; text goes first."""
    batches: list[list[str]] = []
    current = [text_name]
    for f in files:
        if len(current) == MAX_SHARE_FILES:
            batches.append(current)
            current = []
        current.append(f)
    batches.append(current)
    return batches


def mime_for(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif", ".heic": "image/heic", ".avif": "image/avif",
        ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".m4v": "video/mp4",
        ".mkv": "video/x-matroska", ".txt": "text/plain",
    }.get(suffix, "application/octet-stream")


def originals(items: list[MediaItem]) -> list[MediaItem]:
    return [i for i in items if i.path.is_file()]
