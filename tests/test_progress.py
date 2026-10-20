# SPDX-License-Identifier: Apache-2.0
"""Progress of the transcription: from the model's segments to the job the page polls."""

import json
import threading
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import process as process_module
from app import transcribe as transcribe_module
from app.fetch import FetchResult, MediaItem, PostMeta
from app.main import create_app
from app.process import build_pack

from .conftest import make_video, needs_ffmpeg


class FakeModel:
    """Stands in for WhisperModel: four segments of a 40 second clip."""

    def transcribe(self, audio, **options):
        segments = (
            SimpleNamespace(start=s, end=s + 10.0, text=f"part {i}", no_speech_prob=0.1)
            for i, s in enumerate((0.0, 10.0, 20.0, 30.0))
        )
        return segments, SimpleNamespace(language="en", duration=40.0)


def test_transcription_reports_its_progress(monkeypatch, settings, tmp_path):
    monkeypatch.setattr(transcribe_module, "_get_model", lambda settings: FakeModel())
    seen: list[float] = []
    transcript = transcribe_module.transcribe(
        tmp_path / "audio.wav", replace(settings, whisper_model="small"), on_progress=seen.append
    )
    assert transcript.text == "part 0 part 1 part 2 part 3"
    assert seen == [0.25, 0.5, 0.75, 1.0]


@needs_ffmpeg
def test_the_pack_reports_progress_over_all_videos(monkeypatch, settings, tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    items = [MediaItem(make_video(raw / f"v{i}.mp4", seconds=4), "video", i) for i in (1, 2)]
    fetched = FetchResult(items, PostMeta("instagram", "https://www.instagram.com/p/x/"), "fake")

    def fake_transcribe(wav, settings, on_progress=lambda fraction: None):
        on_progress(0.5)
        on_progress(1.0)
        return None

    monkeypatch.setattr(process_module, "transcribe", fake_transcribe)
    seen: list[float] = []
    build_pack(fetched, tmp_path, replace(settings, whisper_model="small"), on_progress=seen.append)
    assert seen == pytest.approx([0.25, 0.5, 0.75, 1.0], abs=0.05)  # two videos of the same length


release = threading.Event()


def runner(job, workdir, settings, set_stage):
    set_stage("transcribing")
    set_stage("transcribing", 0.4)
    release.wait(5)
    return {"files": {}, "packs": {}, "meta": {}, "counts": {}}


def test_the_page_sees_the_progress_but_job_json_does_not_keep_it(settings):
    release.clear()
    with TestClient(create_app(replace(settings, auth_mode="none"), runner=runner), base_url="https://testserver") as client:
        job_id = client.post("/api/jobs", json={"url": "https://www.facebook.com/reel/1/"}).json()["id"]
        deadline = time.time() + 5
        job = client.get(f"/api/jobs/{job_id}").json()
        while job.get("progress") is None and time.time() < deadline:
            time.sleep(0.02)
            job = client.get(f"/api/jobs/{job_id}").json()
        assert (job["stage"], job["progress"]) == ("transcribing", 40)
        saved = json.loads((Path(settings.jobs_dir) / job_id / "job.json").read_text(encoding="utf-8"))
        assert "progress" not in saved  # polled often, not worth a write; old versions could not read it

        release.set()
        while job["status"] != "done" and time.time() < deadline:
            time.sleep(0.02)
            job = client.get(f"/api/jobs/{job_id}").json()
        assert (job["status"], job["progress"]) == ("done", None)
