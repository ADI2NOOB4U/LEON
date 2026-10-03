import json

import pytest

from backend.app.core.planner import PlannerService, planner_service
from backend.app.db.database import get_connection, init_db
from backend.app.jobs.task_manager import create_task, get_task, get_task_artifacts, get_task_logs
from backend.app.jobs.worker import LeonWorker
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


@pytest.fixture(autouse=True)
def clear_database():
    init_db()
    conn = get_connection()
    for table in ("plan_steps", "task_plans", "task_logs", "tasks"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()


class CodingTool(BaseTool):
    name = "coding_execute"
    description = "test coding tool"
    permission = "CONFIRM"

    def __init__(self, results):
        self.results = iter(results)
        self.calls = 0

    async def execute(self, **kwargs):
        self.calls += 1
        return next(self.results)


class FixingCoder:
    provider_name = "mock"

    def __init__(self):
        self.failures = []

    async def implementation_for(self, step, failure=None):
        self.failures.append(failure)
        return {"workspace_path": ".", "command": "pytest", "files": []}


class ConfirmAll:
    def can_execute(self, tool, confirmed=False):
        return True


def make_coding_task(registry):
    task_id = create_task("Implement and verify", max_retries=0)
    PlannerService(registry=registry).create_plan(
        task_id,
        [{"title": "Implement", "description": "Implement and test", "tool_name": "coding_execute", "arguments": {}}],
    )
    return task_id


def test_coding_step_fixes_failure_without_rerunning_completed_work():
    tool = CodingTool([
        {"exit_code": 1, "timed_out": False, "stdout": "test out", "stderr": "first failure"},
        {"exit_code": 0, "timed_out": False, "stdout": "green", "stderr": ""},
    ])
    registry = ToolRegistry()
    registry.register(tool)
    coder = FixingCoder()
    task_id = make_coding_task(registry)

    LeonWorker(registry=registry, permission_manager=ConfirmAll(), coding_agent=coder)._execute(get_task(task_id))

    assert get_task(task_id)["status"] == "completed"
    assert tool.calls == 2
    assert coder.failures[0] is None
    assert "first failure" in coder.failures[1]
    result = json.loads(planner_service.get_plan(task_id)["steps"][0]["result"])
    assert result["stdout"] == "green"


def test_coding_step_fails_cleanly_after_three_fixes_and_captures_output():
    failure = {"exit_code": 2, "timed_out": False, "stdout": "out", "stderr": "broken"}
    tool = CodingTool([failure] * 4)
    registry = ToolRegistry()
    registry.register(tool)
    coder = FixingCoder()
    task_id = make_coding_task(registry)

    LeonWorker(registry=registry, permission_manager=ConfirmAll(), coding_agent=coder)._execute(get_task(task_id))

    task = get_task(task_id)
    assert task["status"] == "failed"
    assert tool.calls == 4
    assert "after 3 fix attempts" in task["error"]
    assert "broken" in task["error"]
    assert len([log for log in get_task_logs(task_id) if log["stage"] == "coding_fix"]) == 3
