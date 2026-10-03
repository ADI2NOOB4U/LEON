import threading
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.db.database import get_connection, init_db
from backend.app.jobs.scheduler import SchedulerService


@pytest.fixture(autouse=True)
def clear_scheduled_jobs():
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM scheduled_jobs")
    conn.commit()
    conn.close()


class RecordingExecutor:
    def __init__(self, fail=False):
        self.jobs = []
        self.fail = fail
        self.event = threading.Event()

    def execute(self, job):
        self.jobs.append(job)
        self.event.set()
        if self.fail:
            raise RuntimeError("scheduled failure")


def test_scheduler_persists_timezone_aware_one_time_job():
    scheduler = SchedulerService(RecordingExecutor())
    run_at = datetime.now(timezone.utc) + timedelta(hours=1)

    job = scheduler.schedule_once("reminder", run_at, {"type": "notification", "title": "Hi", "body": "Later"})

    assert job["status"] == "pending"
    assert datetime.fromisoformat(job["run_at"]).tzinfo is not None
    with pytest.raises(ValueError, match="timezone-aware"):
        scheduler.schedule_once("bad", datetime.now(), {})


def test_scheduler_retries_failed_job_then_marks_it_failed():
    executor = RecordingExecutor(fail=True)
    scheduler = SchedulerService(executor, retry_delay_seconds=1)
    job = scheduler.schedule_once("retry", datetime.now(timezone.utc), {}, max_retries=1)

    scheduler._process(job)
    retried = scheduler.get_job(job["id"])
    assert retried["status"] == "pending"
    assert retried["retry_count"] == 1
    scheduler._process(retried)
    failed = scheduler.get_job(job["id"])
    assert failed["status"] == "failed"
    assert failed["last_error"] == "scheduled failure"


def test_scheduler_reschedules_recurring_job_after_success():
    scheduler = SchedulerService(RecordingExecutor())
    job = scheduler.schedule_recurring("repeat", datetime.now(timezone.utc), 60, {})

    scheduler._process(job)
    updated = scheduler.get_job(job["id"])
    assert updated["status"] == "pending"
    assert datetime.fromisoformat(updated["run_at"]) > datetime.now(timezone.utc)


def test_scheduler_start_executes_due_job_and_stops_cleanly():
    executor = RecordingExecutor()
    scheduler = SchedulerService(executor)
    scheduler.schedule_once("due", datetime.now(timezone.utc), {})

    scheduler.start()
    assert executor.event.wait(timeout=1)
    scheduler.stop()

    assert len(executor.jobs) == 1
    assert scheduler._thread is not None and not scheduler._thread.is_alive()
