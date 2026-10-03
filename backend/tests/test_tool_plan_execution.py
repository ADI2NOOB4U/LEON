import json

import pytest

from backend.app.core.planner import PlannerService, planner_service
from backend.app.db.database import get_connection, init_db
from backend.app.jobs.task_manager import create_task, get_task, get_task_logs
from backend.app.jobs.worker import LeonWorker
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


@pytest.fixture(autouse=True)
def clear_database():
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM plan_steps")
    conn.execute("DELETE FROM task_plans")
    conn.execute("DELETE FROM task_logs")
    conn.execute("DELETE FROM tasks")
    conn.commit()
    conn.close()


def disable_worker_delays(monkeypatch):
    import backend.app.jobs.worker as worker_module

    monkeypatch.setattr(worker_module.time, "sleep", lambda _seconds: None)


class EchoTool(BaseTool):
    name = "echo"
    description = "Return the supplied text."
    permission = "SAFE"

    async def execute(self, text: str, **kwargs):
        if kwargs:
            raise ValueError("unexpected arguments")
        return {"text": text}


class ConfirmTool(EchoTool):
    name = "confirm_echo"
    permission = "CONFIRM"


def test_plan_persists_tool_metadata_and_rejects_unknown_tools():
    registry = ToolRegistry()
    registry.register(EchoTool())
    service = PlannerService(registry=registry)
    task_id = create_task("Use a tool")

    plan = service.create_plan(
        task_id,
        [{"title": "Echo", "description": "Echo a value", "tool_name": "echo", "arguments": {"text": "hello"}}],
    )

    assert plan["steps"][0]["tool_name"] == "echo"
    assert plan["steps"][0]["arguments"] == {"text": "hello"}
    with pytest.raises(ValueError, match="Unknown tool: missing"):
        service.create_plan(
            task_id,
            [{"title": "Bad", "description": "Invalid tool", "tool_name": "missing"}],
        )


def test_worker_executes_registered_tool_stores_result_and_logs(monkeypatch):
    disable_worker_delays(monkeypatch)
    registry = ToolRegistry()
    registry.register(EchoTool())
    task_id = create_task("Use a tool", max_retries=0)
    PlannerService(registry=registry).create_plan(
        task_id,
        [{"title": "Echo", "description": "Echo a value", "tool_name": "echo", "arguments": {"text": "hello"}}],
    )

    LeonWorker(registry=registry)._execute(get_task(task_id))

    step = planner_service.get_plan(task_id)["steps"][0]
    assert step["status"] == "completed"
    assert json.loads(step["result"]) == {"text": "hello"}
    assert "tool_execution" in [log["stage"] for log in get_task_logs(task_id)]


def test_worker_denied_tool_fails_plan_and_preserves_executor(monkeypatch):
    disable_worker_delays(monkeypatch)
    registry = ToolRegistry()
    registry.register(ConfirmTool())
    task_id = create_task("Use a restricted tool", max_retries=0)
    PlannerService(registry=registry).create_plan(
        task_id,
        [{"title": "Restricted", "description": "Needs confirmation", "tool_name": "confirm_echo", "arguments": {"text": "no"}}],
    )

    LeonWorker(registry=registry)._execute(get_task(task_id))

    step = planner_service.get_plan(task_id)["steps"][0]
    assert step["status"] == "failed"
    assert get_task(task_id)["status"] == "failed"

