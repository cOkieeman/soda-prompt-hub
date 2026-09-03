from __future__ import annotations

import time
from threading import Event

from prompt_hub.background_jobs import BackgroundJobRunner, BackgroundJobStore


def _wait_for_status(store: BackgroundJobStore, job_id: str, status: str) -> dict:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        job = store.get(job_id)
        if job is not None and job["status"] == status:
            return job
        time.sleep(0.01)
    message = f"Job {job_id} did not reach {status}"
    raise AssertionError(message)


def test_background_job_store_recovers_interrupted_and_retries(settings) -> None:
    store = BackgroundJobStore(settings.database_path)
    store.initialize()
    created = store.enqueue("scan", {"workspace_id": "one"}, max_attempts=1)
    claimed = store.claim_next({"scan"})
    assert claimed is not None
    assert claimed["job_id"] == created["job_id"]
    assert claimed["status"] == "running"
    assert claimed["attempts"] == 1

    assert store.recover_interrupted() == 1
    recovered = store.get(created["job_id"])
    assert recovered is not None
    assert recovered["status"] == "queued"
    assert recovered["max_attempts"] == 2

    claimed_again = store.claim_next({"scan"})
    assert claimed_again is not None
    store.fail(created["job_id"], "broken source")
    failed = store.get(created["job_id"])
    assert failed is not None
    assert failed["status"] == "failed"
    retried = store.retry(created["job_id"])
    assert retried is not None
    assert retried["status"] == "queued"
    assert retried["error"] == ""

    canceled = store.enqueue("scan", {"workspace_id": "two"})
    canceled = store.request_cancel(canceled["job_id"])
    assert canceled is not None
    assert canceled["status"] == "canceled"


def test_background_runner_auto_retries_and_cancels_running_job(settings) -> None:
    store = BackgroundJobStore(settings.database_path)
    calls = 0

    def flaky(_payload, context):
        nonlocal calls
        calls += 1
        context.update(calls, 2, "attempt")
        if calls == 1:
            message = "first attempt fails"
            raise RuntimeError(message)
        return {"attempts_seen": calls}

    runner = BackgroundJobRunner(store, {"flaky": flaky})
    runner.start()
    try:
        job = runner.submit("flaky", {}, max_attempts=2)
        completed = _wait_for_status(store, job["job_id"], "completed")
        assert completed["attempts"] == 2
        assert completed["result"] == {"attempts_seen": 2}
    finally:
        runner.stop()

    started = Event()

    def wait_for_cancel(_payload, context):
        started.set()
        while True:
            context.update(0, 1, "waiting")
            time.sleep(0.01)

    runner = BackgroundJobRunner(store, {"wait": wait_for_cancel})
    runner.start()
    try:
        job = runner.submit("wait", {})
        assert started.wait(timeout=1)
        store.request_cancel(job["job_id"])
        canceled = _wait_for_status(store, job["job_id"], "canceled")
        assert canceled["cancel_requested"] is True
    finally:
        runner.stop()
