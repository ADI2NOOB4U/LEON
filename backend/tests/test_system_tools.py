from types import SimpleNamespace

import pytest

from backend.app.tools import system_tools
from backend.app.tools.registry import ToolRegistry


@pytest.mark.anyio
async def test_get_time_returns_structured_result():
    result = await system_tools.GetTimeTool().execute()

    assert result["tool"] == "get_time"
    assert result["datetime"]
    assert result["timezone"]


@pytest.mark.anyio
async def test_system_stats_returns_structured_result(monkeypatch):
    monkeypatch.setattr(system_tools.psutil, "cpu_percent", lambda interval=None: 12.5)
    monkeypatch.setattr(
        system_tools.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=100, available=60, used=40, percent=40),
    )
    monkeypatch.setattr(
        system_tools.psutil,
        "disk_usage",
        lambda path: SimpleNamespace(total=200, used=80, free=120, percent=40),
    )

    result = await system_tools.SystemStatsTool().execute()

    assert result["tool"] == "system_stats"
    assert result["cpu_percent"] == 12.5
    assert result["memory"]["used"] == 40
    assert result["disk"]["free"] == 120


@pytest.mark.anyio
async def test_open_app_validates_input(monkeypatch):
    monkeypatch.setattr(system_tools, "sys", SimpleNamespace(platform="win32"))
    tool = system_tools.OpenAppTool()

    with pytest.raises(ValueError):
        await tool.execute(app_name="")
    with pytest.raises(ValueError):
        await tool.execute(app_name="notepad.exe & whoami")


@pytest.mark.anyio
async def test_open_app_uses_startfile_without_shell(monkeypatch):
    opened = []
    monkeypatch.setattr(system_tools, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(system_tools.os, "startfile", opened.append, raising=False)

    result = await system_tools.OpenAppTool().execute(app_name="notepad.exe")

    assert opened == ["notepad.exe"]
    assert result == {"tool": "open_app", "app_name": "notepad.exe", "opened": True}


def test_system_tools_are_registered():
    registry = ToolRegistry()
    system_tools.register_system_tools(registry)

    assert [tool.name for tool in registry.list()] == [
        "get_time",
        "system_stats",
        "open_app",
    ]
