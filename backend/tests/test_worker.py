import pytest

from backend.app.core.planner import planner_service
from backend.app.db.database import get_connection, init_db
from backend.app.jobs.task_manager import create_task, get_task, get_task_logs, request_cancel
from backend.app.jobs.worker import LeonWorker


@pytest.fixture(autouse=True)
def clear_database():
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM plan_steps")
    conn.execute("DELETE FROM task_plans")
    conn.execute("DELETE FROM task_logs")
    conn.execute("DELETE FROM scheduled_jobs")
    conn.execute("DELETE FROM tasks")
    conn.commit()
    conn.close()


def make_plan(task_id):
    return planner_service.create_plan(task_id, ["First", "Second", "Third"])


def disable_worker_delays(monkeypatch):
    import backend.app.jobs.worker as worker_module

    monkeypatch.setattr(worker_module.time, "sleep", lambda _seconds: None)


def test_worker_executes_plan_in_order_and_tracks_progress(monkeypatch):
    disable_worker_delays(monkeypatch)
    task_id = create_task("Prepare a report")
    plan = make_plan(task_id)

    class RecordingExecutor:
        def __init__(self):
            self.titles = []

        def execute(self, step):
            self.titles.append(step["title"])
            return f"Finished {step['title']}"

    executor = RecordingExecutor()
    LeonWorker(executor)._execute(get_task(task_id))

    updated_plan = planner_service.get_plan(task_id)
    task = get_task(task_id)
    logs = get_task_logs(task_id)
    step_transitions = [log["stage"] for log in logs if log["stage"].startswith("step_")]

    assert executor.titles == ["First", "Second", "Third"]
    assert [step["status"] for step in updated_plan["steps"]] == ["completed"] * 3
    assert [step["result"] for step in updated_plan["steps"]] == [
        "Finished First",
        "Finished Second",
        "Finished Third",
    ]
    assert task["status"] == "completed"
    assert task["progress"] == 100
    assert step_transitions == [
        "step_running",
        "step_completed",
        "step_running",
        "step_completed",
        "step_running",
        "step_completed",
    ]
    assert [step["step_number"] for step in plan["steps"]] == [1, 2, 3]


def test_worker_fails_non_tool_steps_without_an_executor():
    task_id = create_task("Unsupported action", max_retries=0)
    plan = make_plan(task_id)

    LeonWorker()._execute(get_task(task_id))

    task = get_task(task_id)
    updated_plan = planner_service.get_plan(task_id)
    assert task["status"] == "failed"
    assert "No executor is configured" in task["error"]
    assert updated_plan["steps"][0]["status"] == "failed"
    assert "Temporary execution completed" not in (task["result"] or "")
    assert plan["steps"][0]["status"] == "pending"


def test_worker_stops_on_failure_and_retries_only_failed_step(monkeypatch):
    disable_worker_delays(monkeypatch)
    task_id = create_task("Prepare a report", max_retries=1)
    make_plan(task_id)

    class FailOnceExecutor:
        def __init__(self):
            self.titles = []
            self.should_fail = True

        def execute(self, step):
            title = step["title"]
            self.titles.append(title)
            if title == "Second" and self.should_fail:
                self.should_fail = False
                raise RuntimeError("temporary step failure")
            return f"Finished {title}"

    executor = FailOnceExecutor()
    worker = LeonWorker(executor)
    worker._execute(get_task(task_id))

    failed_attempt = planner_service.get_plan(task_id)
    assert executor.titles == ["First", "Second"]
    assert get_task(task_id)["status"] == "queued"
    assert [step["status"] for step in failed_attempt["steps"]] == [
        "completed",
        "pending",
        "pending",
    ]

    worker._execute(get_task(task_id))

    completed_plan = planner_service.get_plan(task_id)
    logs = get_task_logs(task_id)
    step_transitions = [log["stage"] for log in logs if log["stage"].startswith("step_")]
    assert executor.titles == ["First", "Second", "Second", "Third"]
    assert [step["status"] for step in completed_plan["steps"]] == ["completed"] * 3
    assert get_task(task_id)["status"] == "completed"
    assert step_transitions == [
        "step_running",
        "step_completed",
        "step_running",
        "step_failed",
        "step_pending",
        "step_running",
        "step_completed",
        "step_running",
        "step_completed",
    ]


def test_worker_keeps_failed_step_failed_after_retry_limit(monkeypatch):
    disable_worker_delays(monkeypatch)
    task_id = create_task("Prepare a report", max_retries=0)
    make_plan(task_id)

    class FailingExecutor:
        def __init__(self):
            self.titles = []

        def execute(self, step):
            self.titles.append(step["title"])
            if step["title"] == "Second":
                raise RuntimeError("permanent step failure")
            return "done"

    executor = FailingExecutor()
    LeonWorker(executor)._execute(get_task(task_id))

    plan = planner_service.get_plan(task_id)
    assert executor.titles == ["First", "Second"]
    assert [step["status"] for step in plan["steps"]] == [
        "completed",
        "failed",
        "pending",
    ]
    assert get_task(task_id)["status"] == "failed"


def test_worker_honors_cancellation_between_steps(monkeypatch):
    disable_worker_delays(monkeypatch)
    task_id = create_task("Prepare a report")
    make_plan(task_id)

    class CancellingExecutor:
        def execute(self, step):
            assert request_cancel(step["task_id"])
            return "Finished current step"

    LeonWorker(CancellingExecutor())._execute(get_task(task_id))

    plan = planner_service.get_plan(task_id)
    assert [step["status"] for step in plan["steps"]] == [
        "completed",
        "pending",
        "pending",
    ]
    assert get_task(task_id)["status"] == "cancelled"
    transitions = [
        log["stage"]
        for log in get_task_logs(task_id)
        if log["stage"].startswith("step_")
    ]
    assert transitions == ["step_running", "step_completed"]
