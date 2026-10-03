import os
import re
import sys
from datetime import datetime
from typing import Any

import psutil

from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


class GetTimeTool(BaseTool):
    name = "get_time"
    description = "Return the current local time."
    permission = "SAFE"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("get_time does not accept arguments")

        current_time = datetime.now().astimezone()
        return {
            "tool": self.name,
            "datetime": current_time.isoformat(),
            "timezone": current_time.tzname(),
        }


class SystemStatsTool(BaseTool):
    name = "system_stats"
    description = "Return CPU, memory, and disk usage statistics."
    permission = "SAFE"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("system_stats does not accept arguments")

        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(os.path.abspath(os.sep))
        return {
            "tool": self.name,
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": memory.percent,
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent,
            },
        }


class OpenAppTool(BaseTool):
    name = "open_app"
    description = "Open a Windows application by executable name."
    permission = "SAFE"

    _APP_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_. -]{0,127}$")

    async def execute(self, app_name: str = "", **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("open_app received unexpected arguments")
        if not isinstance(app_name, str) or not app_name.strip():
            raise ValueError("app_name must be a non-empty string")

        app_name = app_name.strip()
        if (
            not self._APP_NAME_PATTERN.fullmatch(app_name)
            or any(separator in app_name for separator in ("/", "\\", ":"))
        ):
            raise ValueError("app_name must be a simple Windows application name")
        if sys.platform != "win32":
            raise OSError("open_app is only supported on Windows")

        os.startfile(app_name)
        return {
            "tool": self.name,
            "app_name": app_name,
            "opened": True,
        }


def register_system_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register the built-in system tools and return the registry."""
    registry.register(GetTimeTool())
    registry.register(SystemStatsTool())
    registry.register(OpenAppTool())
    return registry


system_registry = register_system_tools(ToolRegistry())
