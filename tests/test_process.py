# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from PIL import Image

from app.fetch import FetchResult, MediaItem, PostMeta, classify_error, _iso_date
from app.process import (
    MAX_SHARE_FILES, build_pack, build_sheet, pick_times, share_batches, tiles_per_sheet,
)

from .conftest import make_image, make_video, needs_ffmpeg


def fetched(items, platform="instagram", caption="Hello caption"):
    meta = PostMeta(platform, "https://www.instagram.com/p/ABC/", author="someone",
                    author_name="Some One", caption=caption, date="2026-10-09")
    return FetchResult(items, meta, "test")


def test_pick_times_spread_and_bounded():
    times = pick_times(60.0, scenes=[3.0, 3.2, 10.0, 31.0, 59.9], count=6)
    assert len(times) == 6
    assert times == sorted(times)
    assert all(0 <= t < 60 for t in times)
    assert min(b - a for a, b in zip(times, times[1:])) >= 1.0


def test_pick_times_short_video():
    assert len(pick_times(1.5, scenes=[], count=1)) == 1
    assert pick_times(0, scenes=[], count=3) == []


def test_tiles_per_sheet():
    assert [tiles_per_sheet(n) for n in (1, 9, 10, 18, 19, 36)] == [1, 1, 2, 2, 4, 4]


def test_share_batches_respect_limit():
    one = share_batches([f"{i:02d}.jpg" for i in range(9)], "post.txt")
    assert len(one) == 1 and one[0][0] == "post.txt" and len(one[0]) == MAX_SHARE_FILES
    two = share_batches([f"{i:02d}.jpg" for i in range(12)], "post.txt")
    assert [len(b) for b in two] == [10, 3]


def test_build_sheet_respects_max_edge(tmp_path: Path):
    paths = [make_image(tmp_path / f"{i}.jpg", str(i)) for i in range(4)]
    dest = tmp_path / "sheet.jpg"
    build_sheet(paths, [1, 2, 3, 4], dest, max_edge=1568)
    with Image.open(dest) as img:
        assert max(img.size) <= 1568
        assert min(img.size) > 600


def test_large_images_are_downscaled(tmp_path: Path, settings):
    raw = tmp_path / "work" / "raw"
    raw.mkdir(parents=True)
    items = [MediaItem(make_image(raw / "big.jpg", "big", size=(3000, 4000)), "image", 1)]
    build_pack(fetched(items), tmp_path / "work", settings)
    with Image.open(tmp_path / "work" / "out" / "01.jpg") as img:
        assert img.size == (1176, 1568)


def test_images_only_pack_with_sheets(tmp_path: Path, settings):
    raw = tmp_path / "work" / "raw"
    raw.mkdir(parents=True)
    items = [MediaItem(make_image(raw / f"{i:02d}.jpg", f"slide {i}"), "image", i) for i in range(1, 13)]
    pack = build_pack(fetched(items), tmp_path / "work", settings)

    assert len(pack.visuals) == 12
    assert len(pack.sheets) == 6  # 12 pictures, 2 per sheet
    with Image.open(tmp_path / "work" / "out" / "01.jpg") as img:
        assert img.size == (1080, 1350)  # small images are never upscaled
    assert "01.jpg: item 1 (image)" in pack.text_full
    assert "sheet-01.jpg combines pictures 1-2" in pack.text_compact
    assert "Author: @someone (Some One)" in pack.text_full
    assert "Hello caption" in pack.text_full


@needs_ffmpeg
def test_video_pack_frames_and_transcript_placeholder(tmp_path: Path, settings):
    raw = tmp_path / "work" / "raw"
    raw.mkdir(parents=True)
    items = [
        MediaItem(make_image(raw / "01.jpg", "cover"), "image", 1),
        MediaItem(make_video(raw / "02.mp4", seconds=12), "video", 2),
        MediaItem(make_video(raw / "03.mp4", seconds=5, audio=False), "video", 3),
    ]
    stages = []
    pack = build_pack(fetched(items), tmp_path / "work", settings, on_stage=stages.append)

    frames = [v for v in pack.visuals if v.kind == "frame"]
    assert 2 <= len([f for f in frames if f.item == 2]) <= settings.max_frames
    assert len([f for f in frames if f.item == 3]) >= 1
    assert not pack.sheets  # few enough pictures for a single share
    assert "(transcription disabled)" in pack.text_full
    assert "(video has no audio track)" in pack.text_full
    assert "frame at 0:" in pack.text_full
    assert stages == ["processing", "transcribing"]
    assert not any((tmp_path / "work" / "tmp").iterdir())


def test_classify_error():
    assert classify_error("[instagram][error] HttpError: '401 Unauthorized'") == "auth_required"
    assert classify_error("ERROR: [Instagram] abc: Requested content is not available, rate-limit reached") == "rate_limited"
    assert classify_error("ERROR: Unsupported URL: https://x") == "unsupported"
    assert classify_error("ProxyError: Unable to connect to proxy (403 Forbidden)") == "unreachable"
    assert classify_error("something odd") == "download_failed"


def test_iso_date():
    assert _iso_date("20261009") == "2026-10-09"
    assert _iso_date("2026-10-09 12:34:56") == "2026-10-09"
    assert _iso_date(0) == "1970-01-01"
    assert _iso_date(None) == ""


def test_fmt_time_truncates_like_the_app():
    from app.process import fmt_time
    assert [fmt_time(t) for t in (0.5, 1.99, 59.9, 61.0)] == ["0:00", "0:01", "0:59", "1:01"]
