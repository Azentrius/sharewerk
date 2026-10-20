# SPDX-License-Identifier: Apache-2.0
"""The pause between Instagram downloads that protects the account the cookies belong to."""

import time
from dataclasses import replace

import pytest

from app.config import load_settings
from app.jobs import JobStore
from app.urls import Target

starts: list[tuple[str, float]] = []


def runner(job, workdir, settings, set_stage):
    starts.append((job.key, time.monotonic()))
    return {"files": {}, "packs": {}, "meta": {}, "counts": {}}


def instagram(key: str) -> Target:
    return Target(f"https://www.instagram.com/p/{key}/", "instagram", "post", key)


def facebook(key: str) -> Target:
    return Target(f"https://www.facebook.com/reel/{key}/", "facebook", "reel", key)


def finished(store: JobStore, job_id: str, timeout: float = 5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = store.get(job_id)
        if job.status in {"done", "error"}:
            return job
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} is still {store.get(job_id).status}")


def started(key: str) -> float:
    return next(t for k, t in starts if k == key)


@pytest.fixture
def make_store(settings):
    starts.clear()
    stores = []

    def make(pause: int | float) -> JobStore:
        store = JobStore(replace(settings, instagram_pause_seconds=pause), runner)
        store.start()
        stores.append(store)
        return store

    yield make
    for store in stores:
        store.stop()


def test_instagram_downloads_keep_the_pause(make_store):
    store = make_store(0.6)
    first, second = store.submit(instagram("first")), store.submit(instagram("second"))
    assert finished(store, first.id).status == "done"
    assert finished(store, second.id).status == "done"
    assert started("second") - started("first") >= 0.55


def test_a_waiting_job_says_why(make_store):
    store = make_store(1.0)
    finished(store, store.submit(instagram("first")).id)
    second = store.submit(instagram("second"))
    deadline = time.time() + 0.8
    while store.get(second.id).stage != "waiting" and time.time() < deadline:
        time.sleep(0.02)
    job = store.get(second.id)
    assert (job.status, job.stage) == ("running", "waiting")
    assert finished(store, second.id).status == "done"


def test_facebook_does_not_wait_for_instagram(make_store):
    store = make_store(5)
    finished(store, store.submit(instagram("first")).id)
    finished(store, store.submit(facebook("reel")).id, timeout=2)
    assert started("reel") - started("first") < 2


def test_no_pause_when_switched_off(make_store):
    store = make_store(0)
    finished(store, store.submit(instagram("first")).id)
    finished(store, store.submit(instagram("second")).id, timeout=2)
    assert started("second") - started("first") < 1


def test_stop_ends_a_pause(make_store):
    store = make_store(30)
    finished(store, store.submit(instagram("first")).id)
    store.submit(instagram("second"))
    time.sleep(0.2)
    store.stop()
    deadline = time.time() + 2
    while store.problem() != "worker_stopped" and time.time() < deadline:
        time.sleep(0.02)
    assert store.problem() == "worker_stopped"
    assert [k for k, _ in starts] == ["first"]


def test_the_pause_is_configurable(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHAREWERK_AUTH_MODE", "none")
    assert load_settings().instagram_pause_seconds == 20
    monkeypatch.setenv("SHAREWERK_INSTAGRAM_PAUSE", "45")
    assert load_settings().instagram_pause_seconds == 45
