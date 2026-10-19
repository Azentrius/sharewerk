# SPDX-License-Identifier: Apache-2.0
import subprocess

import pytest

from .conftest import needs_ffmpeg


@needs_ffmpeg
def test_whisper_decodes_audio_with_the_installed_pyav(tmp_path):
    """faster-whisper reads audio through PyAV. PyAV 19 dropped an argument that
    faster-whisper 1.2.1 passes, which broke every transcription (requirements.txt)."""
    audio = pytest.importorskip("faster_whisper.audio")
    wav = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=1", "-ac", "1", "-ar", "16000", str(wav)],
        check=True, timeout=60,
    )
    samples = audio.decode_audio(str(wav), sampling_rate=16000)
    assert 15_000 < len(samples) < 17_000
