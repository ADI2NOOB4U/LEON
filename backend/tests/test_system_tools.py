from types import SimpleNamespace

import pytest

from backend.app.tools import system_tools
from backend.app.tools.registry import ToolRegistry


@pytest.mark.anyio
async def test_get_datetime_returns_structured_result():
    result = await system_tools.GetDatetimeTool().execute()

    assert result["tool"] == "get_datetime"
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
    with pytest.raises(ValueError):
        await tool.execute(app_name="notepad.exe /x")


@pytest.mark.anyio
async def test_open_app_uses_startfile_without_shell(monkeypatch):
    opened = []
    monkeypatch.setattr(system_tools, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(system_tools.os, "startfile", opened.append, raising=False)

    result = await system_tools.OpenAppTool().execute(app_name="notepad.exe")

    assert opened == ["notepad.exe"]
    assert result == {"tool": "open_app", "app_name": "notepad.exe", "opened": True}


@pytest.mark.anyio
async def test_list_processes_returns_structured_result(monkeypatch):
    monkeypatch.setattr(
        system_tools.psutil,
        "process_iter",
        lambda attrs: [
            SimpleNamespace(
                info={"pid": 123, "name": "leon.exe", "status": "running", "username": "user"}
            )
        ],
    )

    result = await system_tools.ListProcessesTool().execute()

    assert result == {
        "tool": "list_processes",
        "processes": [{"pid": 123, "name": "leon.exe", "status": "running", "username": "user"}],
        "count": 1,
    }


@pytest.mark.anyio
async def test_open_url_validates_and_uses_default_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(
        system_tools.webbrowser,
        "open",
        lambda url, new: opened.append((url, new)) or True,
    )
    tool = system_tools.OpenUrlTool()

    with pytest.raises(ValueError):
        await tool.execute(url="file:///C:/Windows/System32")
    with pytest.raises(ValueError):
        await tool.execute(url="https://example.com\nhttps://attacker.invalid")

    result = await tool.execute(url="https://example.com/path?q=1")

    assert opened == [("https://example.com/path?q=1", 2)]
    assert result == {"tool": "open_url", "url": "https://example.com/path?q=1", "opened": True}


def test_system_tools_are_registered():
    registry = ToolRegistry()
    system_tools.register_system_tools(registry)

    assert [tool.name for tool in registry.list()] == [
        "get_datetime",
        "system_stats",
        "list_processes",
        "open_app",
        "open_url",
        "open_browser",
        "get_page_title",
        "extract_page_text",
        "search_web",
        "git_status",
        "git_log",
        "git_diff",
        "git_branch_list",
        "coding_execute",
        "send_email",
        "send_task_result",
        "list_directory",
        "read_file",
        "create_file",
        "edit_file",
        "create_directory",
    ]


def test_read_only_tools_are_safe_and_launch_tools_require_confirmation():
    registry = ToolRegistry()
    system_tools.register_system_tools(registry)

    assert registry.get("get_datetime").permission == "SAFE"
    assert registry.get("system_stats").permission == "SAFE"
    assert registry.get("list_processes").permission == "SAFE"
    assert registry.get("open_app").permission == "CONFIRM"
    assert registry.get("open_url").permission == "CONFIRM"
    assert registry.get("open_browser").permission == "CONFIRM"
    assert registry.get("get_page_title").permission == "SAFE"
    assert registry.get("extract_page_text").permission == "SAFE"
    assert registry.get("search_web").permission == "SAFE"
    assert registry.get("git_status").permission == "SAFE"
    assert registry.get("git_log").permission == "SAFE"
    assert registry.get("git_diff").permission == "SAFE"
    assert registry.get("git_branch_list").permission == "SAFE"
    assert registry.get("coding_execute").permission == "CONFIRM"
    assert registry.get("send_email").permission == "CONFIRM"
    assert registry.get("send_task_result").permission == "CONFIRM"
