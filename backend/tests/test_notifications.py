import pytest

from backend.app.db.database import get_connection, init_db
from backend.app.jobs.task_manager import create_task, get_task_logs, get_task
from backend.app.jobs.worker import LeonWorker
from backend.app.notifications.providers import MockNotificationProvider
from backend.app.notifications.service import NotificationService


@pytest.fixture(autouse=True)
def clear_database():
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM task_logs")
    conn.execute("DELETE FROM tasks")
    conn.commit()
    conn.close()


def disable_worker_delays(monkeypatch):
    import backend.app.jobs.worker as worker_module

    monkeypatch.setattr(worker_module.time, "sleep", lambda _seconds: None)


def test_worker_notifies_on_task_completion(monkeypatch):
    disable_worker_delays(monkeypatch)
    task_id = create_task("Finish report")
    provider = MockNotificationProvider()

    LeonWorker(notifications=NotificationService(provider))._execute(get_task(task_id))

    assert provider.notifications[0]["title"] == "LEON task completed: Finish report"
    assert "notification_sent" in [entry["stage"] for entry in get_task_logs(task_id)]


def test_worker_notifies_on_final_task_failure(monkeypatch):
    disable_worker_delays(monkeypatch)
    task_id = create_task("Fail report", max_retries=0)
    provider = MockNotificationProvider()

    class FailingExecutor:
        def execute(self, step):
            raise RuntimeError("failure")

    from backend.app.core.planner import planner_service

    planner_service.create_plan(task_id, ["Only step"])
    LeonWorker(FailingExecutor(), notifications=NotificationService(provider))._execute(get_task(task_id))

    assert provider.notifications[0]["title"] == "LEON task failed: Fail report"
    assert "notification_sent" in [entry["stage"] for entry in get_task_logs(task_id)]


def test_notification_delivery_failure_is_audited_without_raising():
    class FailingProvider:
        def send(self, title, body):
            raise RuntimeError("desktop unavailable")

    task_id = create_task("Notification failure")
    sent = NotificationService(FailingProvider()).notify_task_outcome(get_task(task_id), "completed")

    assert sent is False
    assert "notification_failed" in [entry["stage"] for entry in get_task_logs(task_id)]
