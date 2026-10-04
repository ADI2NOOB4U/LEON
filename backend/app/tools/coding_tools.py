"""A constrained, workspace-only executor for development work."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from backend.app.config.settings import settings
from backend.app.tools.base import BaseTool
from backend.app.tools.filesystem_tools import CreateFileTool, EditFileTool
from backend.app.tools.registry import ToolRegistry


# Values are fixed argv sequences, never shell fragments or user-provided arguments.
ALLOWED_COMMANDS: dict[str, tuple[str, ...]] = {
    "pytest": (sys.executable, "-m", "pytest"),
    "compileall": (sys.executable, "-m", "compileall", "."),
}
MAX_TIMEOUT_SECONDS = 300
MAX_OUTPUT_BYTES = 1_000_000


class CodingExecutorTool(BaseTool):
    name = "coding_execute"
    description = "Create/edit workspace files and run one allowlisted development command."
    permission = "CONFIRM"

    def __init__(self, workspace_root: Path | None = None) -> None:
        self._workspace_root = Path(workspace_root or settings.workspace_dir).resolve()
        self._file_tools = {
            "create": CreateFileTool((self._workspace_root,)),
            "edit": EditFileTool((self._workspace_root,)),
        }

    def _resolve_workspace(self, workspace_path: str) -> Path:
        if not isinstance(workspace_path, str) or not workspace_path.strip():
            raise ValueError("workspace_path must be a non-empty string")
        if "\x00" in workspace_path:
            raise ValueError("workspace_path must not contain null bytes")
        requested = Path(workspace_path)
        if not requested.is_absolute():
            requested = self._workspace_root / requested
        resolved = requested.resolve(strict=False)
        if not resolved.is_relative_to(self._workspace_root):
            raise ValueError("workspace_path must be inside the configured workspace")
        if not resolved.is_dir():
            raise ValueError("workspace_path must be an existing directory")
        return resolved

    @staticmethod
    def _validate_files(files: list[dict[str, str]] | None) -> list[dict[str, str]]:
        if files is None:
            return []
        if not isinstance(files, list):
            raise ValueError("files must be a list")
        if len(files) > 100:
            raise ValueError("files may contain at most 100 changes")
        validated = []
        for change in files:
            if not isinstance(change, dict) or set(change) != {"action", "path", "content"}:
                raise ValueError("each file change requires only action, path, and content")
            if change["action"] not in {"create", "edit"}:
                raise ValueError("file action must be create or edit")
            if not isinstance(change["path"], str) or not isinstance(change["content"], str):
                raise ValueError("file path and content must be strings")
            validated.append(change)
        return validated

    async def execute(
        self,
        workspace_path: str = ".",
        command: str = "",
        files: list[dict[str, str]] | None = None,
        timeout_seconds: int = 60,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if kwargs:
            raise ValueError("coding_execute received unexpected arguments")
        if command not in ALLOWED_COMMANDS:
            raise ValueError(f"command must be one of: {', '.join(ALLOWED_COMMANDS)}")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS
        ):
            raise ValueError(f"timeout_seconds must be an integer between 1 and {MAX_TIMEOUT_SECONDS}")

        workspace = self._resolve_workspace(workspace_path)
        changes = self._validate_files(files)
        workspace_file_tools = {
            "create": CreateFileTool((workspace,)),
            "edit": EditFileTool((workspace,)),
        }
        file_results = []
        for change in changes:
            file_results.append(
                await workspace_file_tools[change["action"]].execute(
                    path=change["path"], content=change["content"]
                )
            )

        execution = await self._run_command(ALLOWED_COMMANDS[command], workspace, timeout_seconds)
        return {
            "tool": self.name,
            "workspace_path": str(workspace),
            "command": command,
            "files": file_results,
            **execution,
        }

    async def _run_command(
        self, argv: tuple[str, ...], workspace: Path, timeout_seconds: int
    ) -> dict[str, Any]:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        communication = asyncio.create_task(process.communicate())
        timed_out = False
        try:
            stdout, stderr = await asyncio.wait_for(
                asyncio.shield(communication), timeout=timeout_seconds
            )
        except TimeoutError:
            timed_out = True
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                process.kill()
                await process.wait()
            stdout, stderr = await communication

        return {
            "exit_code": process.returncode,
            "timed_out": timed_out,
            "stdout": self._bounded_output(stdout),
            "stderr": self._bounded_output(stderr),
        }

    @staticmethod
    def _bounded_output(output: bytes) -> str:
        if len(output) > MAX_OUTPUT_BYTES:
            output = output[:MAX_OUTPUT_BYTES] + b"\n[output truncated]"
        return output.decode("utf-8", errors="replace")


def register_coding_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register the confirmation-gated coding executor."""
    registry.register(CodingExecutorTool())
    return registry
