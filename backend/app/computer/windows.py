from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional
import psutil

from backend.app.tools.applications import APPLICATIONS, resolve_application


def get_active_window_info() -> Dict[str, Any]:
    """Return the active foreground window title and associated process info."""
    title = ""
    app_name = None
    pid = None

    if sys.platform == "win32":
        try:
            import ctypes
            import ctypes.wintypes

            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value

                proc_id = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
                pid = proc_id.value
                if pid:
                    try:
                        p = psutil.Process(pid)
                        app_name = p.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        except Exception:
            pass

    # Fallback to scanning running allowlisted applications if title is empty
    if not title or not app_name:
        running = list_running_applications()
        if running:
            app_name = running[0]
            title = f"{running[0]} (Active Session)"

    # Resolve friendly name
    display_name = app_name
    if app_name:
        resolved = resolve_application(app_name)
        if resolved:
            display_name = resolved.display_name

    return {
        "title": title or "Desktop",
        "process_name": app_name,
        "display_name": display_name or "Desktop",
        "pid": pid,
    }


def list_running_applications() -> List[str]:
    """Return a list of running allowlisted applications."""
    running: set[str] = set()
    candidate_map = {}
    for app in APPLICATIONS:
        for c in app.candidates:
            candidate_map[c.casefold()] = app.display_name

    for process in psutil.process_iter(["name"]):
        try:
            name = str(process.info.get("name") or "").casefold()
            if name in candidate_map:
                running.add(candidate_map[name])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return sorted(list(running))


def focus_window_by_title(partial_title: str) -> bool:
    """Attempt to bring a window matching partial_title to foreground."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        import ctypes.wintypes

        EnumWindows = ctypes.windll.user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        GetWindowText = ctypes.windll.user32.GetWindowTextW
        SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
        ShowWindow = ctypes.windll.user32.ShowWindow

        matched_hwnd = None
        target_norm = partial_title.lower()

        def enum_cb(hwnd: int, lparam: int) -> bool:
            nonlocal matched_hwnd
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buf, length + 1)
                if target_norm in buf.value.lower():
                    matched_hwnd = hwnd
                    return False  # stop enumeration
            return True

        EnumWindows(EnumWindowsProc(enum_cb), 0)
        if matched_hwnd:
            ShowWindow(matched_hwnd, 9)  # SW_RESTORE
            SetForegroundWindow(matched_hwnd)
            return True
    except Exception:
        pass
    return False
