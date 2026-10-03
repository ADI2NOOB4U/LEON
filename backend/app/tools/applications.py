"""Small, explicit application registry used by open_app."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class Application:
    key: str
    display_name: str
    candidates: tuple[str, ...]


APPLICATIONS = (
    Application("vscode", "VS Code", ("Code.exe", "code.exe")),
    Application("chrome", "Chrome", ("chrome.exe",)),
    Application("edge", "Edge", ("msedge.exe",)),
    Application("spotify", "Spotify", ("Spotify.exe",)),
    Application("vlc", "VLC", ("vlc.exe",)),
    Application("discord", "Discord", ("Discord.exe",)),
    Application("steam", "Steam", ("steam.exe",)),
    Application("notepad", "Notepad", ("notepad.exe",)),
    Application("explorer", "File Explorer", ("explorer.exe",)),
)


def resolve_application(name: str) -> Application | None:
    normalized = (name or "").strip().lower().replace(" ", "")
    for app in APPLICATIONS:
        if normalized in {app.key, app.display_name.lower().replace(" ", ""), *(c.lower().removesuffix(".exe") for c in app.candidates)}:
            return app
    return None


def installed_executable(app: Application) -> str | None:
    for candidate in app.candidates:
        found = shutil.which(candidate)
        if found:
            return found
    if os.name != "nt":
        return None
    roots = [
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
        Path(os.environ.get("LOCALAPPDATA", "")),
        Path(os.environ.get("APPDATA", "")),
    ]
    user_local_app_data = Path.home() / "AppData" / "Local"
    if user_local_app_data not in roots:
        roots.append(user_local_app_data)
    folders = {"vscode": ("Microsoft VS Code",), "chrome": ("Google", "Chrome"), "edge": ("Microsoft", "Edge"), "spotify": ("Spotify",), "vlc": ("VideoLAN", "VLC"), "discord": ("Discord",), "steam": ("Steam",)}.get(app.key, ())
    locations = [(root, folders) for root in roots]
    if app.key == "vscode":
        local_app_data_roots: list[Path] = []
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            local_app_data_roots.append(Path(local_app_data))
        if user_local_app_data not in local_app_data_roots:
            local_app_data_roots.append(user_local_app_data)
        locations.extend(
            (root, ("Programs", "Microsoft VS Code"))
            for root in local_app_data_roots
        )
    for root, relative_folders in locations:
        candidate_root = root.joinpath(*relative_folders) if relative_folders else root
        if not candidate_root.is_dir():
            continue
        for candidate in app.candidates:
            matches = list(candidate_root.rglob(candidate))
            if matches:
                return str(matches[0])
    candidate_names = {candidate.casefold() for candidate in app.candidates}
    for process in psutil.process_iter(["name", "exe"]):
        try:
            info = process.info
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        if str(info.get("name") or "").casefold() in candidate_names:
            executable = info.get("exe")
            if isinstance(executable, str) and executable:
                return executable
    return None
