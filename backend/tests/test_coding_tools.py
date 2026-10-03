import asyncio
from pathlib import Path

import pytest

from backend.app.security.permissions import PermissionManager
from backend.app.tools.coding_tools import CodingExecutorTool


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    path = tmp_path / "workspace"
    path.mkdir()
    return path


@pytest.mark.anyio
async def test_coding_executor_edits_only_workspace_files_and_returns_result(workspace, monkeypatch):
    tool = CodingExecutorTool(workspace)

    async def fake_run(argv, cwd, timeout):
        assert cwd == workspace
        assert argv[-2:] == ("compileall", ".")
        assert timeout == 20
        return {"exit_code": 0, "timed_out": False, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr(tool, "_run_command", fake_run)
    result = await tool.execute(
        command="compileall",
        timeout_seconds=20,
        files=[{"action": "create", "path": "app.py", "content": "print('ok')\n"}],
    )

    assert (workspace / "app.py").read_text(encoding="utf-8") == "print('ok')\n"
    assert result["files"][0]["tool"] == "create_file"
    assert result["exit_code"] == 0


@pytest.mark.anyio
async def test_coding_executor_rejects_shell_like_commands_and_outside_paths(workspace, monkeypatch):
    tool = CodingExecutorTool(workspace)
    monkeypatch.setattr(tool, "_run_command", lambda *args: pytest.fail("must not run"))

    with pytest.raises(ValueError, match="command must be one of"):
        await tool.execute(command="pytest; whoami")
    with pytest.raises(ValueError, match="configured workspace"):
        await tool.execute(workspace_path="..", command="pytest")
    with pytest.raises(ValueError, match="create or edit"):
        await tool.execute(command="pytest", files=[{"action": "delete", "path": "a", "content": ""}])


@pytest.mark.anyio
async def test_coding_executor_uses_exec_argv_and_captures_output(workspace, monkeypatch):
    captured = {}

    class Process:
        returncode = 3

        async def communicate(self):
            return b"standard output", b"standard error"

    async def fake_create(*argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        return Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    result = await CodingExecutorTool(workspace)._run_command(("python", "-m", "pytest"), workspace, 5)

    assert captured["argv"] == ("python", "-m", "pytest")
    assert captured["cwd"] == str(workspace)
    assert result == {"exit_code": 3, "timed_out": False, "stdout": "standard output", "stderr": "standard error"}


@pytest.mark.anyio
async def test_coding_executor_terminates_timed_out_process(workspace, monkeypatch):
    released = asyncio.Event()

    class Process:
        def __init__(self):
            self.returncode = None
            self.terminated = False

        async def communicate(self):
            await released.wait()
            return b"partial output", b"timed out"

        def terminate(self):
            self.terminated = True
            self.returncode = -15
            released.set()

        async def wait(self):
            return self.returncode

        def kill(self):
            pytest.fail("terminate should have cleaned up the process")

    process = Process()

    async def fake_create(*argv, **kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    result = await CodingExecutorTool(workspace)._run_command(("pytest",), workspace, 0.01)

    assert process.terminated is True
    assert result == {"exit_code": -15, "timed_out": True, "stdout": "partial output", "stderr": "timed out"}


def test_coding_executor_requires_confirmation():
    assert not PermissionManager().can_execute(CodingExecutorTool(Path.cwd()))
