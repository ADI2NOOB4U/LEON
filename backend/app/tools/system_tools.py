import os
import re
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any
from urllib.parse import urlsplit

import psutil

from backend.app.tools.base import BaseTool
from backend.app.tools.browser_tools import register_browser_tools
from backend.app.tools.coding_tools import register_coding_tools
from backend.app.tools.email_tools import register_email_tools
from backend.app.tools.filesystem_tools import register_filesystem_tools
from backend.app.tools.git_tools import register_git_tools
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.applications import resolve_application, installed_executable
from backend.app.security.web_security import WebSecurityError, validate_public_url


class GetDatetimeTool(BaseTool):
    name = "get_datetime"
    description = "Return the actual current date and time for the local system or a named IANA timezone."
    permission = "SAFE"

    async def execute(self, timezone_name: str = "", include_utc: bool = False, **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("get_datetime received unexpected arguments")
        try:
            zone = ZoneInfo(timezone_name.strip()) if timezone_name.strip() else datetime.now().astimezone().tzinfo
        except ZoneInfoNotFoundError as exc:
            # Windows installations without the optional tzdata wheel still get
            # deterministic support for common fixed-offset requests.
            fixed_zones = {
                "UTC": timezone.utc,
                "Etc/UTC": timezone.utc,
                "Asia/Kolkata": timezone(timedelta(hours=5, minutes=30), "IST"),
                "Asia/Tokyo": timezone(timedelta(hours=9), "JST"),
            }
            try:
                zone = fixed_zones[timezone_name.strip()]
            except KeyError:
                raise ValueError("timezone_name must be a valid IANA timezone") from exc
        current_time = datetime.now(zone)
        utc_time = datetime.now(timezone.utc)
        return {
            "tool": self.name,
            "datetime": current_time.isoformat(),
            "date": current_time.date().isoformat(),
            "time": current_time.strftime("%H:%M:%S"),
            "day_of_week": current_time.strftime("%A"),
            "timezone": timezone_name.strip() or getattr(current_time.tzinfo, "key", None) or current_time.tzname(),
            "utc": utc_time.isoformat() if include_utc else None,
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
        if sys.platform != "win32":
            raise OSError("open_app is only supported on Windows")

        application = resolve_application(app_name)
        if application:
            launch_target = installed_executable(application)
        else:
            if (
                not self._APP_NAME_PATTERN.fullmatch(app_name)
                or any(separator in app_name for separator in ("/", "\\", ":"))
            ):
                raise ValueError("app_name must be a simple Windows application name")
            launch_target = app_name
        if not launch_target:
            raise FileNotFoundError(f"Application not found: {app_name}")
        os.startfile(launch_target)
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

        try:
            url = validate_public_url(url.strip())
        except WebSecurityError as exc:
            raise ValueError(str(exc)) from exc

        opened = webbrowser.open(url, new=2)
        return {"tool": self.name, "url": url, "opened": opened}


def register_system_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register the built-in system tools and return the registry."""
    registry.register(GetDatetimeTool())
    registry.register(SystemStatsTool())
    registry.register(ListProcessesTool())
    registry.register(OpenAppTool())
    registry.register(OpenUrlTool())
    register_browser_tools(registry)
    register_git_tools(registry)
    register_coding_tools(registry)
    register_email_tools(registry)
    register_filesystem_tools(registry)
    return registry


system_registry = register_system_tools(ToolRegistry())
