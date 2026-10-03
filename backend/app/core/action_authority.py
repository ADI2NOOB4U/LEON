"""The only application-level gateway from a proposed action to a tool."""
from __future__ import annotations

from typing import Any

from backend.app.security.permissions import PermissionLevel, PermissionManager
from backend.app.tools.registry import ToolRegistry


class ActionAuthority:
    def __init__(self, registry: ToolRegistry, permission_manager: PermissionManager | None = None):
        self.registry = registry
        self.permissions = permission_manager or PermissionManager()

    async def execute(self, tool_name: str, arguments: dict[str, Any] | None = None, *, confirmed: bool = False) -> Any:
        tool = self.registry.get(tool_name)
        if tool is None:
            raise PermissionError("TARGET_NOT_FOUND")
        try:
            level = PermissionLevel(tool.permission)
        except (AttributeError, TypeError, ValueError) as exc:
            raise PermissionError("ACTION_BLOCKED") from exc
        if level == PermissionLevel.BLOCKED or not self.permissions.can_execute(tool, confirmed=confirmed):
            raise PermissionError("ACTION_BLOCKED" if level == PermissionLevel.BLOCKED else "PERMISSION_REQUIRED")
        return await self.registry.execute(tool_name, **(arguments or {}))
