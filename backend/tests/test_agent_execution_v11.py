import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.planner import PlannerService, planner_service
from backend.app.db.database import get_connection, init_db
from backend.app.jobs.task_manager import create_task, get_task, get_task_logs, recover_interrupted_tasks
from backend.app.jobs.worker import LeonWorker
from backend.app.notifications.providers import MockNotificationProvider
from backend.app.notifications.service import NotificationService
from backend.app.security.permissions import PermissionManager
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


@pytest.fixture(autouse=True)
def clean_tasks():
    init_db()
    conn = get_connection()
    for table in ("plan_steps", "task_plans", "task_logs", "tasks"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()


class EchoTool(BaseTool):
    name = "e2e_echo"
    description = "Echo text"
    permission = "SAFE"

    async def execute(self, text: str):
        return {"text": text}


def test_command_task_runs_plan_steps_verifies_and_notifies(monkeypatch):
    monkeypatch.setattr("backend.app.jobs.worker.time.sleep", lambda _: None)
    registry = ToolRegistry()
    registry.register(EchoTool())
    task_id = create_task("Run the end-to-end task", max_retries=0)
    PlannerService(registry=registry).create_plan(
        task_id,
        [{"title": "Echo", "description": "Echo input", "tool_name": "e2e_echo", "arguments": {"text": "ok"}}],
    )
    notifications = MockNotificationProvider()

    LeonWorker(registry=registry, notifications=NotificationService(notifications))._execute(get_task(task_id))

    task = get_task(task_id)
    assert task["status"] == "completed", (task, get_task_logs(task_id))
    assert task["progress"] == 100
    assert "1 step" in task["result"]
    assert json.loads(planner_service.get_plan(task_id)["steps"][0]["result"]) == {"text": "ok"}
    assert notifications.notifications


def test_command_current_datetime_persists_and_executes_tool_plan():
    response = TestClient(app).post(
        "/api/command",
        json={"message": "Leon, tell me the current date and time"},
    )
    assert response.status_code == 200
    task_id = response.json()["task"]["id"]

    plan = planner_service.get_plan(task_id)
    assert plan is not None
    assert [(step["tool_name"], step["arguments"]) for step in plan["steps"]] == [
        ("get_datetime", {})
    ]

    LeonWorker()._execute(get_task(task_id))

    task = get_task(task_id)
    step = planner_service.get_plan(task_id)["steps"][0]
    actual_result = json.loads(step["result"])
    assert step["status"] == "completed"
    assert actual_result["tool"] == "get_datetime"
    assert actual_result["datetime"] in task["result"]
    assert task["result"] != "Task 'Leon, tell me the current date and time' completed successfully (1 step)."


def test_restart_requeues_running_work_without_rerunning_completed_steps():
    task_id = create_task("Recover task")
    planner_service.create_plan(task_id, ["Already done", "Resume me"])
    plan = planner_service.get_plan(task_id)
    planner_service.update_step(plan["steps"][0]["id"], "completed", "done")
    planner_service.update_step(plan["steps"][1]["id"], "running")
    from backend.app.jobs.task_manager import update_task
    update_task(task_id, status="executing", current_stage="executing")

    assert recover_interrupted_tasks() == 1
    assert get_task(task_id)["status"] == "queued"
    assert [step["status"] for step in planner_service.get_plan(task_id)["steps"]] == ["completed", "pending"]


def test_permission_is_checked_before_registered_tool_execution():
    registry = ToolRegistry()
    registry.register(EchoTool())
    task_id = create_task("Denied task", max_retries=0)
    PlannerService(registry=registry).create_plan(
        task_id,
        [{"title": "Echo", "description": "Echo input", "tool_name": "e2e_echo", "arguments": {"text": "no"}}],
    )

    class DenyAll(PermissionManager):
        def can_execute(self, tool, confirmed=False):
            return False

    LeonWorker(registry=registry, permission_manager=DenyAll())._execute(get_task(task_id))

    assert get_task(task_id)["status"] == "failed"
    assert "cannot be executed" in get_task(task_id)["error"]
    assert "tool_execution" not in [entry["stage"] for entry in get_task_logs(task_id)]
