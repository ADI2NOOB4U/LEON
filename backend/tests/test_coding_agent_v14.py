import json
from pathlib import Path

import pytest

from backend.app.config.settings import settings
from backend.app.core.coding_agent import CodingAgent
from backend.app.core.planner import PlannerService, planner_service
from backend.app.db.database import get_connection, init_db
from backend.app.jobs.task_manager import create_task, get_task
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
    description = "Test coding executor"
    permission = "CONFIRM"

    def __init__(self):
        self.arguments = None

    async def execute(self, **kwargs):
        self.arguments = kwargs
        return {"exit_code": 0, "timed_out": False, "stdout": "ok", "stderr": ""}


class CoderRouter:
    provider_name = "ollama"

    def __init__(self):
        self.roles = []
        self.prompt = ""

    async def chat(self, messages, role="general"):
        self.roles.append(role)
        self.prompt = messages[1]["content"]
        return json.dumps(
            {
                "workspace_path": ".",
                "command": "compileall",
                "files": [
                    {"action": "edit", "path": "app.py", "content": "print('new')\n"}
                ],
            }
        )


def test_coding_flow_inspects_then_implements_and_verifies(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "app.py").write_text("print('old')\n", encoding="utf-8")
    monkeypatch.setattr(settings, "workspace_dir", workspace)

    router = CoderRouter()
    coding_agent = CodingAgent(router)
    coding_tool = CodingTool()
    registry = ToolRegistry()
    registry.register(coding_tool)

    task_id = create_task("Implement the app", max_retries=0)
    PlannerService(registry=registry).create_plan(
        task_id,
        [
            {
                "title": "Implement app",
                "description": "Update the existing app and run the build.",
                "tool_name": "coding_execute",
                "arguments": {
                    "workspace_path": ".",
                    "command": "compileall",
                    "files": [
                        {"action": "edit", "path": "app.py", "content": "placeholder"}
                    ],
                },
            }
        ],
    )

    class ConfirmAll:
        def can_execute(self, tool, confirmed=False):
            return True

    LeonWorker(
        registry=registry,
        permission_manager=ConfirmAll(),
        coding_agent=coding_agent,
    )._execute(get_task(task_id))

    assert router.roles == ["coding"]
    assert "app.py" in router.prompt
    assert "print('old')" in router.prompt
    assert coding_tool.arguments["files"][0]["content"] == "print('new')\n"
    assert get_task(task_id)["status"] == "completed"
    assert planner_service.get_plan(task_id)["steps"][0]["status"] == "completed"
