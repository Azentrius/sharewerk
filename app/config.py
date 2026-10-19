# SPDX-License-Identifier: Apache-2.0
"""Runtime configuration, read once from environment variables.

Every setting has a SHAREWERK_ prefix. See .env.example for documentation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ALLOWED_HOSTS = (
    "instagram.com",
    "www.instagram.com",
    "m.instagram.com",
    "instagr.am",
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "web.facebook.com",
    "fb.watch",
    "fb.com",
)


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


def _list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return tuple(h.strip().lower() for h in raw.split(",") if h.strip())


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    auth_mode: str = "token"  # "token" or "none"
    auth_token: str = ""
    data_dir: Path = Path("/data")
    cookies_file: Path = Path("/secrets/cookies.txt")
    gallery_dl_config: Path = Path("/secrets/gallery-dl.conf")
    whisper_model: str = "small"  # tiny|base|small|medium|large-v3|off
    whisper_language: str = ""  # empty = auto-detect
    whisper_threads: int = 0  # 0 = let CTranslate2 decide
    image_max_edge: int = 1568
    max_frames: int = 8
    max_video_seconds: int = 900
    max_items: int = 20
    max_download_mb: int = 500
    retention_hours: int = 24
    allowed_hosts: tuple[str, ...] = field(default=DEFAULT_ALLOWED_HOSTS)
    cookie_secure: bool = True

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def transcription_enabled(self) -> bool:
        return self.whisper_model.lower() not in {"", "off", "none", "false", "0"}

    def validate(self) -> None:
        if self.auth_mode not in {"token", "none"}:
            raise ConfigError("SHAREWERK_AUTH_MODE must be 'token' or 'none'.")
        if self.auth_mode == "token" and len(self.auth_token) < 24:
            raise ConfigError(
                "SHAREWERK_AUTH_TOKEN must be set (at least 24 characters) when "
                "SHAREWERK_AUTH_MODE=token. Generate one with: openssl rand -hex 32. "
                "Only use SHAREWERK_AUTH_MODE=none behind an authenticating proxy."
            )
        if self.image_max_edge < 256:
            raise ConfigError("SHAREWERK_IMAGE_MAX_EDGE must be at least 256.")


def load_settings() -> Settings:
    s = Settings(
        auth_mode=os.environ.get("SHAREWERK_AUTH_MODE", "token").strip().lower(),
        auth_token=os.environ.get("SHAREWERK_AUTH_TOKEN", "").strip(),
        data_dir=Path(os.environ.get("SHAREWERK_DATA_DIR", "/data")),
        cookies_file=Path(os.environ.get("SHAREWERK_COOKIES_FILE", "/secrets/cookies.txt")),
        gallery_dl_config=Path(
            os.environ.get("SHAREWERK_GALLERY_DL_CONFIG", "/secrets/gallery-dl.conf")
        ),
        whisper_model=os.environ.get("SHAREWERK_WHISPER_MODEL", "small").strip(),
        whisper_language=os.environ.get("SHAREWERK_WHISPER_LANGUAGE", "").strip(),
        whisper_threads=_int("SHAREWERK_WHISPER_THREADS", 0),
        image_max_edge=_int("SHAREWERK_IMAGE_MAX_EDGE", 1568),
        max_frames=_int("SHAREWERK_MAX_FRAMES", 8),
        max_video_seconds=_int("SHAREWERK_MAX_VIDEO_SECONDS", 900),
        max_items=_int("SHAREWERK_MAX_ITEMS", 20),
        max_download_mb=_int("SHAREWERK_MAX_DOWNLOAD_MB", 500),
        retention_hours=_int("SHAREWERK_RETENTION_HOURS", 24),
        allowed_hosts=_list("SHAREWERK_ALLOWED_HOSTS", DEFAULT_ALLOWED_HOSTS),
        cookie_secure=_bool("SHAREWERK_COOKIE_SECURE", True),
    )
    s.validate()
    return s
