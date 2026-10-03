"""Coder-model orchestration for workspace-scoped implementation steps."""

from __future__ import annotations

import json
from typing import Any

from backend.app.config.settings import settings
from backend.app.core.router import ModelRouter
from backend.app.tools.filesystem_tools import ListDirectoryTool, ReadFileTool


class CodingAgent:
    """Turn a planned coding step into validated coding-tool arguments."""

    def __init__(self, router: ModelRouter | None = None) -> None:
        self.router = router or ModelRouter()
        roots = (settings.workspace_dir,)
        self._list_directory = ListDirectoryTool(roots)
        self._read_file = ReadFileTool(roots)

    async def implementation_for(
        self, step: dict[str, Any], failure: str | None = None
    ) -> dict[str, Any]:
        arguments = step.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError("Coding step arguments must be an object")

        # Inspect before every implementation, including deterministic mock
        # execution, so the workspace safety invariant is provider-independent.
        inspection = await self._inspect(arguments)

        # Mock mode has no coder model. Keep deterministic local execution for
        # tests and for the existing built-in mock workflow.
        if self.router.provider_name == "mock":
            return arguments
        prompt = {
            "step": {
                "title": step.get("title", ""),
                "description": step.get("description", ""),
            },
            "workspace": inspection,
            "previous_failure": failure or "",
        }
        response = await self.router.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are LEON's coding implementation agent. Return only JSON "
                        "for the coding_execute tool with exactly these keys: "
                        "workspace_path, command, files. command must be pytest or "
                        "compileall. files must contain only create/edit actions with "
                        "path and content. Use paths relative to the workspace. Do "
                        "not use shell commands or access files outside the workspace."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt)},
            ],
            role="coding",
        )
        return self._validate_response(response)

    async def _inspect(self, arguments: dict[str, Any]) -> dict[str, Any]:
        listing = await self._list_directory.execute(path=".")
        files = []
        for change in arguments.get("files", []):
            if not isinstance(change, dict) or change.get("action") != "edit":
                continue
            path = change.get("path")
            if isinstance(path, str):
                files.append(await self._read_file.execute(path=path))
        return {"listing": listing, "files": files}

    @staticmethod
    def _validate_response(response: str) -> dict[str, Any]:
        try:
            value = json.loads(response)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("Coder returned invalid JSON") from exc
        if not isinstance(value, dict) or set(value) != {
            "workspace_path", "command", "files"
        }:
            raise ValueError("Coder response must contain only workspace_path, command, files")
        if value["command"] not in {"pytest", "compileall"}:
            raise ValueError("Coder returned a command that is not allowlisted")
        if not isinstance(value["workspace_path"], str) or not isinstance(value["files"], list):
            raise ValueError("Coder response has invalid coding arguments")
        for change in value["files"]:
            if (
                not isinstance(change, dict)
                or set(change) != {"action", "path", "content"}
                or change["action"] not in {"create", "edit"}
                or not isinstance(change["path"], str)
                or not isinstance(change["content"], str)
            ):
                raise ValueError("Coder returned invalid file changes")
        return value
