from pathlib import Path

import pytest

from backend.app.security.permissions import PermissionManager
from backend.app.tools.filesystem_tools import (
    CreateDirectoryTool,
    CreateFileTool,
    EditFileTool,
    ListDirectoryTool,
    ReadFileTool,
)
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.system_tools import register_system_tools


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    data = tmp_path / "data"
    workspace.mkdir()
    data.mkdir()
    return workspace, data


@pytest.mark.anyio
async def test_list_directory_and_read_file_return_structured_results(roots):
    workspace, data = roots
    file_path = workspace / "notes.txt"
    file_path.write_text("hello LEON", encoding="utf-8")
    (data / "cache").mkdir()

    listing = await ListDirectoryTool(roots).execute(path=".")
    content = await ReadFileTool(roots).execute(path=str(file_path))

    assert listing == {
        "tool": "list_directory",
        "path": str(workspace.resolve()),
        "entries": [{"name": "notes.txt", "type": "file"}],
        "count": 1,
    }
    assert content == {
        "tool": "read_file",
        "path": str(file_path.resolve()),
        "content": "hello LEON",
    }


@pytest.mark.anyio
async def test_filesystem_tools_block_paths_outside_allowed_roots(roots, tmp_path):
    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("secret", encoding="utf-8")
    tools = [
        ListDirectoryTool(roots),
        ReadFileTool(roots),
        CreateFileTool(roots),
        EditFileTool(roots),
        CreateDirectoryTool(roots),
    ]

    for tool in tools:
        with pytest.raises(ValueError, match="configured LEON directory"):
            if tool.name == "create_file":
                await tool.execute(path="../secret.txt", content="blocked")
            else:
                await tool.execute(path=str(outside_file))


@pytest.mark.anyio
async def test_create_file_never_overwrites_and_create_directory_requires_new_path(roots):
    workspace, _ = roots
    file_tool = CreateFileTool(roots)
    directory_tool = CreateDirectoryTool(roots)

    created_file = await file_tool.execute(path="new.txt", content="first")
    created_directory = await directory_tool.execute(path="reports")

    assert created_file == {
        "tool": "create_file",
        "path": str((workspace / "new.txt").resolve()),
        "created": True,
        "bytes_written": 5,
    }
    assert created_directory == {
        "tool": "create_directory",
        "path": str((workspace / "reports").resolve()),
        "created": True,
    }
    with pytest.raises(ValueError, match="will not be overwritten"):
        await file_tool.execute(path="new.txt", content="replacement")
    assert (workspace / "new.txt").read_text(encoding="utf-8") == "first"
    with pytest.raises(ValueError, match="already exists"):
        await directory_tool.execute(path="reports")


@pytest.mark.anyio
async def test_edit_file_only_updates_existing_utf8_file(roots):
    workspace, _ = roots
    file_path = workspace / "existing.txt"
    file_path.write_text("before", encoding="utf-8")

    result = await EditFileTool(roots).execute(path="existing.txt", content="after")

    assert result["edited"] is True
    assert file_path.read_text(encoding="utf-8") == "after"
    with pytest.raises(ValueError, match="existing file"):
        await EditFileTool(roots).execute(path="missing.txt", content="new")


@pytest.mark.anyio
async def test_filesystem_tools_validate_arguments_and_permissions(roots):
    manager = PermissionManager()
    read_tool = ReadFileTool(roots)
    write_tool = CreateFileTool(roots)

    assert manager.can_execute(read_tool)
    assert not manager.can_execute(write_tool)
    assert manager.can_execute(write_tool, confirmed=True)
    with pytest.raises(ValueError, match="content must be a string"):
        await write_tool.execute(path="file.txt", content=1)
    with pytest.raises(ValueError, match="unexpected arguments"):
        await read_tool.execute(path="file.txt", unexpected=True)


def test_filesystem_tools_are_registered():
    registry = ToolRegistry()
    register_system_tools(registry)

    assert [tool.name for tool in registry.list()][-5:] == [
        "list_directory",
        "read_file",
        "create_file",
        "edit_file",
        "create_directory",
    ]
