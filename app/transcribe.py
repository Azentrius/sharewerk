# SPDX-License-Identifier: Apache-2.0
"""Speech-to-text with faster-whisper (CTranslate2, runs on the CPU).

The model is loaded lazily on first use and cached for the life of the process.
It is downloaded once from Hugging Face into SHAREWERK_DATA_DIR/models.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

from .config import Settings

log = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()

# Segments the model itself considers "probably not speech" (music, noise).
# Whisper tends to hallucinate text on music, so these are dropped.
NO_SPEECH_THRESHOLD = 0.6


@dataclass
class Transcript:
    language: str
    segments: list[tuple[float, str]]

    @property
    def text(self) -> str:
        return " ".join(t for _, t in self.segments).strip()


def _get_model(settings: Settings):
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel  # heavy import, keep it lazy

            settings.models_dir.mkdir(parents=True, exist_ok=True)
            log.info("loading whisper model %s (first run downloads it)", settings.whisper_model)
            _model = WhisperModel(
                settings.whisper_model,
                device="cpu",
                compute_type="int8",
                cpu_threads=settings.whisper_threads,
                download_root=str(settings.models_dir),
            )
        return _model


def transcribe(audio: Path, settings: Settings, on_progress=lambda fraction: None) -> Transcript | None:
    """on_progress gets the share of the audio done so far (0 to 1) after every segment."""
    if not settings.transcription_enabled:
        return None
    model = _get_model(settings)
    segments, info = model.transcribe(
        str(audio),
        language=settings.whisper_language or None,
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=False,
    )
    kept: list[tuple[float, str]] = []
    for seg in segments:  # a generator: the model works while we iterate
        if info.duration:
            on_progress(min(1.0, float(seg.end) / info.duration))
        text = seg.text.strip()
        if not text or seg.no_speech_prob > NO_SPEECH_THRESHOLD:
            continue
        kept.append((float(seg.start), text))
    if not kept:
        return Transcript(info.language, [])
    return Transcript(info.language, kept)
