from enum import StrEnum
from typing import Callable

from backend.app.tools.base import BaseTool


class PermissionLevel(StrEnum):
    SAFE = "SAFE"
    CONFIRM = "CONFIRM"
    BLOCKED = "BLOCKED"


class PermissionManager:
    """Determine whether a tool may be executed."""

    def __init__(self) -> None:
        self.rules: dict[PermissionLevel, Callable[[bool], bool]] = {
            PermissionLevel.SAFE: lambda confirmed: True,
            PermissionLevel.CONFIRM: lambda confirmed: confirmed,
            PermissionLevel.BLOCKED: lambda confirmed: False,
        }

    def can_execute(self, tool: BaseTool, confirmed: bool = False) -> bool:
        """Return whether ``tool`` may execute under the current confirmation."""
        try:
            level = PermissionLevel(tool.permission)
        except (AttributeError, ValueError, TypeError):
            return False

        return self.rules[level](confirmed)
