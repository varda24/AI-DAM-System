from app.services import analysis_jobs


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