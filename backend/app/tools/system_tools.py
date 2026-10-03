import os
import re
import sys
import webbrowser
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

import psutil

from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


class GetDatetimeTool(BaseTool):
    name = "get_datetime"
    description = "Return the current local date, time, and timezone."
    permission = "SAFE"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("get_datetime does not accept arguments")

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
    permission = "CONFIRM"

    _APP_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

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


class ListProcessesTool(BaseTool):
    name = "list_processes"
    description = "Return details for currently running processes."
    permission = "SAFE"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("list_processes does not accept arguments")

        processes: list[dict[str, Any]] = []
        for process in psutil.process_iter(["pid", "name", "status", "username"]):
            try:
                info = process.info
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                continue

            processes.append(
                {
                    "pid": info.get("pid"),
                    "name": info.get("name"),
                    "status": info.get("status"),
                    "username": info.get("username"),
                }
            )

        return {"tool": self.name, "processes": processes, "count": len(processes)}


class OpenUrlTool(BaseTool):
    name = "open_url"
    description = "Open an HTTP or HTTPS URL in the default browser."
    permission = "CONFIRM"

    _URL_PATTERN = re.compile(r"^https?://[^\s/?#]+(?:[^\s]*)$", re.IGNORECASE)

    async def execute(self, url: str = "", **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("open_url received unexpected arguments")
        if not isinstance(url, str) or not url.strip():
            raise ValueError("url must be a non-empty string")

        url = url.strip()
        parsed = urlsplit(url)
        try:
            port = parsed.port
        except ValueError:
            port = None
            valid_port = False
        else:
            valid_port = port is None or 0 < port < 65536
        if (
            not self._URL_PATTERN.fullmatch(url)
            or "\\" in url
            or parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or not valid_port
        ):
            raise ValueError("url must be a valid HTTP or HTTPS URL")

        opened = webbrowser.open(url, new=2)
        return {"tool": self.name, "url": url, "opened": opened}


def register_system_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register the built-in system tools and return the registry."""
    registry.register(GetDatetimeTool())
    registry.register(SystemStatsTool())
    registry.register(ListProcessesTool())
    registry.register(OpenAppTool())
    registry.register(OpenUrlTool())
    return registry


system_registry = register_system_tools(ToolRegistry())
