# SPDX-License-Identifier: Apache-2.0
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.config import Settings

TOKEN = "t" * 40

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        auth_mode="token",
        auth_token=TOKEN,
        data_dir=tmp_path / "data",
        cookies_file=tmp_path / "missing-cookies.txt",
        gallery_dl_config=tmp_path / "missing-gallery-dl.conf",
        whisper_model="off",
        cookie_secure=False,
        instagram_pause_seconds=0,  # tests/test_pause.py sets it where it matters
    )


def make_image(path: Path, label: str, size=(1080, 1350), color=(30, 60, 120)) -> Path:
    img = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(img)
    draw.rectangle((40, 40, size[0] - 40, size[1] - 40), outline=(250, 204, 21), width=12)
    draw.text((100, 100), label, fill=(255, 255, 255))
    img.save(path, "JPEG", quality=90)
    return path


def make_video(path: Path, seconds: int = 12, audio: bool = True) -> Path:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", f"testsrc2=s=480x600:d={seconds}:r=25"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast"]
    if audio:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd.append(str(path))
    subprocess.run(cmd, check=True, timeout=120)
    return path
