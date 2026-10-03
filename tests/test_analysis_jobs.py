import threading
import time

import pytest

from app.services import analysis_jobs


def _stop_worker(timeout: float = 2.0) -> None:
    analysis_jobs._worker_stop.set()
    analysis_jobs._work_available.set()
    deadline = time.monotonic() + timeout
    while analysis_jobs._worker_running and time.monotonic() < deadline:
        time.sleep(0.01)
    analysis_jobs._worker_stop.clear()
    analysis_jobs._work_available.clear()


def _wait_until(predicate, timeout: float = 2.0, message: str = "timed out") -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError(message)


@pytest.fixture(autouse=True)
def stop_analysis_worker_after_test():
    yield
    _stop_worker()


def test_drain_pending_jobs_continues_until_queue_is_empty(monkeypatch):
    batches = iter((100, 100, 4))
    calls = []

    def process_pending_jobs(limit: int) -> int:
        calls.append(limit)
        return next(batches)

    monkeypatch.setattr(analysis_jobs, "process_pending_jobs", process_pending_jobs)

    processed = analysis_jobs.drain_pending_jobs(batch_size=100)

    assert processed == 204
    assert calls == [100, 100, 100]


def test_drain_pending_jobs_stops_when_first_batch_is_partial(monkeypatch):
    calls = []

    def process_pending_jobs(limit: int) -> int:
        calls.append(limit)
        return 3

    monkeypatch.setattr(analysis_jobs, "process_pending_jobs", process_pending_jobs)

    processed = analysis_jobs.drain_pending_jobs(batch_size=100)

    assert processed == 3
    assert calls == [100]


def test_idle_worker_processes_a_later_pending_job(monkeypatch):
    lock = threading.Lock()
    pending = [1, 2, 3]
    processed: list[int] = []

    def process_pending_jobs(limit: int) -> int:
        count = 0
        with lock:
            while count < limit and pending:
                processed.append(pending.pop(0))
                count += 1
        return count

    monkeypatch.setattr(analysis_jobs, "process_pending_jobs", process_pending_jobs)

    analysis_jobs.start_analysis_worker()
    _wait_until(
        lambda: processed == [1, 2, 3],
        message="initial pending jobs were not drained",
    )

    with lock:
        pending.append(4)
    analysis_jobs.start_analysis_worker()
    _wait_until(
        lambda: processed == [1, 2, 3, 4],
        message="idle worker did not pick up the newly queued job",
    )


def test_start_analysis_worker_starts_only_one_thread(monkeypatch):
    created: list[threading.Thread] = []
    real_thread = threading.Thread

    def tracking_thread(*args, **kwargs):
        thread = real_thread(*args, **kwargs)
        created.append(thread)
        return thread

    monkeypatch.setattr(analysis_jobs.threading, "Thread", tracking_thread)
    monkeypatch.setattr(analysis_jobs, "drain_pending_jobs", lambda batch_size=100: 0)

    analysis_jobs.start_analysis_worker()
    analysis_jobs.start_analysis_worker()

    _wait_until(lambda: analysis_jobs._worker_running, message="worker did not start")
    named = [thread for thread in threading.enumerate() if thread.name == "ai-dam-analysis-worker"]
    assert len(created) == 1
    assert len(named) == 1


def test_start_during_idle_transition_does_not_strand_pending_job(monkeypatch):
    lock = threading.Lock()
    pending = [1]
    processed: list[int] = []
    first_drain_done = threading.Event()
    release_first_drain = threading.Event()
    drain_calls = 0

    def drain_pending_jobs(batch_size: int = 100) -> int:
        nonlocal drain_calls
        drain_calls += 1
        count = 0
        with lock:
            while count < batch_size and pending:
                processed.append(pending.pop(0))
                count += 1
        if drain_calls == 1:
            first_drain_done.set()
            release_first_drain.wait(timeout=2)
        return count

    monkeypatch.setattr(analysis_jobs, "drain_pending_jobs", drain_pending_jobs)

    analysis_jobs.start_analysis_worker()
    assert first_drain_done.wait(timeout=2)

    with lock:
        pending.append(2)
    analysis_jobs.start_analysis_worker()
    release_first_drain.set()

    _wait_until(
        lambda: 2 in processed,
        message="PENDING job was stranded across the idle/shutdown window",
    )
    named = [thread for thread in threading.enumerate() if thread.name == "ai-dam-analysis-worker"]
    assert len(named) == 1
