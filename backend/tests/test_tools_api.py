from fastapi.testclient import TestClient

from backend.app.api import tools as tools_api
from backend.app.main import app
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry

client = TestClient(app)


class PermissionTestTool(BaseTool):
    description = "Permission test tool"

    def __init__(self, name: str, permission: str) -> None:
        self.name = name
        self.permission = permission

    async def execute(self, **kwargs: object) -> dict[str, str]:
        return {"status": "executed"}


def test_list_tools():
    response = client.get("/api/tools")

    assert response.status_code == 200
    assert [tool["name"] for tool in response.json()] == [
        "get_time",
        "system_stats",
        "open_app",
    ]


def test_execute_tool_returns_result():
    response = client.post(
        "/api/tools/get_time",
        json={"arguments": {}, "confirmed": False},
    )

    assert response.status_code == 200
    assert response.json()["tool"] == "get_time"


def test_unknown_tool_returns_clear_error():
    response = client.post(
        "/api/tools/missing",
        json={"arguments": {}, "confirmed": False},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown tool: missing"


def test_confirmation_required_tool_returns_clear_error(monkeypatch):
    registry = ToolRegistry()
    registry.register(PermissionTestTool("confirm_tool", "CONFIRM"))
    monkeypatch.setattr(tools_api, "registry", registry)

    response = client.post(
        "/api/tools/confirm_tool",
        json={"arguments": {}, "confirmed": False},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Confirmation required for tool 'confirm_tool'"


def test_confirmed_tool_executes(monkeypatch):
    registry = ToolRegistry()
    registry.register(PermissionTestTool("confirm_tool", "CONFIRM"))
    monkeypatch.setattr(tools_api, "registry", registry)

    response = client.post(
        "/api/tools/confirm_tool",
        json={"arguments": {}, "confirmed": True},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "executed"}


def test_blocked_tool_returns_clear_error(monkeypatch):
    registry = ToolRegistry()
    registry.register(PermissionTestTool("blocked_tool", "BLOCKED"))
    monkeypatch.setattr(tools_api, "registry", registry)

    response = client.post(
        "/api/tools/blocked_tool",
        json={"arguments": {}, "confirmed": True},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Tool 'blocked_tool' is blocked"
