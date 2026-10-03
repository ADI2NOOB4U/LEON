"""Safe local media control with provider discovery and verification."""
from __future__ import annotations

import os
import subprocess
import asyncio
import json
import re
import secrets
import time
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlencode
import httpx

from .applications import installed_executable, resolve_application
from .base import BaseTool
from .registry import ToolRegistry
from backend.app.config.settings import settings

MEDIA_ACTIONS = {"play", "pause", "resume", "stop", "next", "previous", "current", "volume", "search"}
SPOTIFY_API = "https://api.spotify.com/v1"
SPOTIFY_ACCOUNTS = "https://accounts.spotify.com"
SPOTIFY_SCOPES = "user-read-playback-state user-modify-playback-state"


class SpotifyError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 503):
        super().__init__(message)
        self.code, self.status_code = code, status_code


def _norm(value: str) -> str:
    return " ".join((value or "").casefold().replace("’", "'").split())


class SpotifyOAuth:
    def __init__(self) -> None:
        self._state: str | None = None
        self._frontend_return_url = settings.frontend_base_url.rstrip("/")
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(settings.spotify_client_id.strip() and settings.spotify_client_secret.get_secret_value().strip())

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(settings.spotify_token_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
            return {}

    def _write(self, token: dict[str, Any]) -> None:
        path = settings.spotify_token_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                handle.write(json.dumps(token, separators=(",", ":")))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def disconnect(self) -> None:
        try:
            settings.spotify_token_path.unlink()
        except FileNotFoundError:
            pass

    def authorization_url(self, frontend_return_url: str | None = None) -> str:
        self._state = secrets.token_urlsafe(32)
        self._frontend_return_url = (frontend_return_url or settings.frontend_base_url).rstrip("/")
        params = {"client_id": settings.spotify_client_id, "response_type": "code", "redirect_uri": settings.spotify_redirect_uri, "scope": SPOTIFY_SCOPES, "state": self._state}
        return f"{SPOTIFY_ACCOUNTS}/authorize?{urlencode(params)}"

    def frontend_return_url(self, state: str) -> str:
        if self._state and secrets.compare_digest(self._state, state):
            return self._frontend_return_url
        return settings.frontend_base_url.rstrip("/")

    async def callback(self, code: str, state: str) -> None:
        if not self._state or not secrets.compare_digest(self._state, state):
            raise ValueError("Invalid Spotify OAuth state.")
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(f"{SPOTIFY_ACCOUNTS}/api/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": settings.spotify_redirect_uri}, auth=(settings.spotify_client_id, settings.spotify_client_secret.get_secret_value()))
        response.raise_for_status()
        token = response.json()
        if not token.get("access_token"):
            raise SpotifyError("SPOTIFY_TOKEN_INVALID", "Spotify token exchange returned no access token.", 502)
        token["expires_at"] = time.time() + int(token.get("expires_in", 3600))
        self._write(token)
        self._state = None

    async def access_token(self) -> str | None:
        if not self.configured:
            return None
        token = self._read()
        if token.get("access_token") and float(token.get("expires_at", 0)) > time.time() + 30:
            return str(token["access_token"])
        refresh = token.get("refresh_token")
        if not refresh:
            return None
        async with self._lock:
            token = self._read()
            if token.get("access_token") and float(token.get("expires_at", 0)) > time.time() + 30:
                return str(token["access_token"])
            async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
                response = await client.post(f"{SPOTIFY_ACCOUNTS}/api/token", data={"grant_type": "refresh_token", "refresh_token": refresh}, auth=(settings.spotify_client_id, settings.spotify_client_secret.get_secret_value()))
            response.raise_for_status()
            refreshed = response.json()
            refreshed.setdefault("refresh_token", refresh)
            refreshed["expires_at"] = time.time() + int(refreshed.get("expires_in", 3600))
            self._write(refreshed)
            return str(refreshed.get("access_token"))

    async def request(self, method: str, path: str, *, token: str, **kwargs: Any) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.request(method, f"{SPOTIFY_API}{path}", headers={"Authorization": f"Bearer {token}"}, **kwargs)
        if response.status_code == 204:
            return {}
        if response.status_code == 401:
            raise SpotifyError("SPOTIFY_AUTH_REQUIRED", "Spotify authorization expired; reconnect Spotify.", 401)
        if response.status_code == 403:
            raise SpotifyError("SPOTIFY_PLAYBACK_FORBIDDEN", "Spotify playback control requires Premium and playback permission.", 403)
        if response.status_code == 429:
            raise SpotifyError("SPOTIFY_RATE_LIMITED", "Spotify is rate limiting requests. Try again shortly.", 429)
        response.raise_for_status()
        return response.json() if response.content else {}

    async def status(self) -> dict[str, Any]:
        token_path = settings.spotify_token_path
        token_file_exists = token_path.is_file()
        stored = self._read()
        if not self.configured:
            return {"configured": False, "authenticated": False, "requires_auth": True, "error_code": "SPOTIFY_NOT_CONFIGURED"}
        if not stored:
            return {"configured": True, "authenticated": False, "requires_auth": True, "error_code": "SPOTIFY_TOKEN_MISSING" if not token_file_exists else "SPOTIFY_TOKEN_INVALID"}
        try:
            token = await self.access_token()
        except (httpx.HTTPError, SpotifyError, ValueError, TypeError, OSError):
            return {"configured": True, "authenticated": False, "requires_auth": True, "error_code": "SPOTIFY_TOKEN_REFRESH_FAILED"}
        result: dict[str, Any] = {"configured": True, "authenticated": bool(token), "requires_auth": not bool(token)}
        if not token:
            result["error_code"] = "SPOTIFY_TOKEN_INVALID"
            return result
        try:
            devices = await self.request("GET", "/me/player/devices", token=token)
            account = await self.request("GET", "/me", token=token)
            available = [device for device in devices.get("devices", []) if not device.get("is_restricted")]
            current = next((device for device in available if device.get("is_active")), None)
            result.update(
                account_authorized=True,
                account_name=account.get("display_name") or account.get("id"),
                devices_available=len(available),
                device_available=bool(available),
                device_name=current.get("name") if current else (available[0].get("name") if available else None),
            )
        except SpotifyError as exc:
            result.update(authenticated=False, requires_auth=True, account_authorized=False,
                          error_code="SPOTIFY_TOKEN_INVALID" if exc.status_code == 401 else exc.code)
        except httpx.HTTPError:
            result.update(authenticated=False, requires_auth=True, account_authorized=False,
                          error_code="SPOTIFY_STATUS_UNAVAILABLE")
        return result


spotify_oauth = SpotifyOAuth()


class MediaProvider(ABC):
    name = "unknown"

    @abstractmethod
    async def execute(self, action: str, query: str = "", **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError


class UnavailableMediaProvider(MediaProvider):
    name = "none"

    async def execute(self, action: str, query: str = "", **kwargs: Any) -> dict[str, Any]:
        return {"success": False, "state": "UNAVAILABLE", "provider": self.name,
                "code": "MEDIA_UNAVAILABLE", "message": "No supported local media provider is available."}


class WindowsMediaProvider(MediaProvider):
    """Optional Windows Global System Media Transport Controls provider."""
    name = "windows_media"

    def __init__(self, manager: Any):
        self.manager = manager

    @classmethod
    async def discover(cls) -> "WindowsMediaProvider | None":
        if os.name != "nt":
            return None
        try:
            from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
            manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
            if manager is not None and manager.get_current_session() is not None:
                return cls(manager)
        except (ImportError, AttributeError, RuntimeError, OSError):
            return None
        return None

    async def _state(self, session) -> dict[str, Any]:
        properties = await session.try_get_media_properties_async()
        playback = session.get_playback_info()
        status = str(getattr(playback, "playback_status", "")).lower()
        state = "PLAYING" if "playing" in status else "PAUSED" if "paused" in status else "STOPPED"
        return {"success": True, "state": state, "provider": self.name,
                "title": getattr(properties, "title", "") or None,
                "artist": getattr(properties, "artist", "") or None}

    async def execute(self, action: str, query: str = "", **kwargs: Any) -> dict[str, Any]:
        session = self.manager.get_current_session()
        if session is None:
            return {"success": False, "state": "IDLE", "provider": self.name,
                    "code": "MEDIA_UNAVAILABLE", "message": "No active media session was detected."}
        if action == "current":
            return await self._state(session)
        calls = {"pause": "try_pause_async", "resume": "try_play_async", "play": "try_play_async",
                 "stop": "try_stop_async", "next": "try_next_async", "previous": "try_previous_async"}
        method_name = calls.get(action)
        method = getattr(session, method_name, None) if method_name else None
        if method is None:
            return {"success": False, "state": "ERROR", "provider": self.name,
                    "code": "UNSUPPORTED_OPERATION", "message": "The active provider does not expose that operation."}
        if not await method():
            return {"success": False, "state": "ERROR", "provider": self.name,
                    "code": "PLAYBACK_FAILED", "message": f"The provider rejected {action}."}
        result = await self._state(session)
        if action in {"play", "resume"} and result.get("state") != "PLAYING":
            result.update(success=False, code="PLAYBACK_NOT_VERIFIED", message="Playback could not be verified.")
        return result


class SpotifyProvider(MediaProvider):
    name = "spotify"

    @classmethod
    def discover(cls) -> "SpotifyProvider | None":
        app = resolve_application("spotify")
        return cls() if app and installed_executable(app) else None

    async def execute(self, action: str, query: str = "", **kwargs: Any) -> dict[str, Any]:
        token = await spotify_oauth.access_token()
        if not token:
            return {"success": False, "state": "UNAVAILABLE", "provider": self.name, "code": "SPOTIFY_AUTH_REQUIRED", "message": "Connect Spotify before controlling playback."}
        try:
            if action == "search":
                return {"success": True, "state": "SEARCHED", "provider": self.name, "tracks": await self._search(token, query)}
            if action == "play":
                return await self._play(token, query)
            if action in {"pause", "resume", "stop", "next", "previous", "volume"}:
                return await self._control(token, action, kwargs.get("volume"))
            if action == "current":
                return await self._current(token)
            return {"success": False, "state": "ERROR", "provider": self.name, "code": "UNSUPPORTED_OPERATION", "message": "Unsupported Spotify action."}
        except SpotifyError as exc:
            return {"success": False, "state": "ERROR", "provider": self.name, "code": exc.code, "message": str(exc)}

    async def _search(self, token: str, query: str) -> list[dict[str, Any]]:
        data = await spotify_oauth.request("GET", "/search", token=token, params={"q": query, "type": "track", "limit": 10})
        tracks = data.get("tracks", {}).get("items", [])
        return [{"id": item.get("id"), "uri": item.get("uri"), "name": item.get("name"), "artists": [a.get("name") for a in item.get("artists", [])]} for item in tracks]

    async def _resolve_track(self, token: str, query: str) -> dict[str, Any] | None:
        cleaned = re.sub(r"^\s*(?:play|start|put on|listen to)\s+", "", query, flags=re.IGNORECASE)
        title, _, artist = cleaned.partition(" by ")
        search_query = f'track:"{title.strip()}"' + (f' artist:"{artist.strip()}"' if artist.strip() else "")
        tracks = await self._search(token, search_query)
        wanted_title, wanted_artist = _norm(title), _norm(artist)
        exact = [t for t in tracks if _norm(t.get("name", "")) == wanted_title and (not wanted_artist or any(_norm(a) == wanted_artist for a in t.get("artists", [])))]
        return (exact or tracks or [None])[0]

    async def _devices(self, token: str) -> list[dict[str, Any]]:
        return (await spotify_oauth.request("GET", "/me/player/devices", token=token)).get("devices", [])

    async def _play(self, token: str, query: str) -> dict[str, Any]:
        track = await self._resolve_track(token, query)
        if not track or not track.get("uri"):
            return {"success": False, "state": "ERROR", "provider": self.name, "code": "SPOTIFY_TRACK_NOT_FOUND", "message": "Spotify could not find that track."}
        devices = await self._devices(token)
        usable = [d for d in devices if not d.get("is_restricted")]
        if not usable:
            app = resolve_application("spotify")
            executable = installed_executable(app) if app else None
            if executable:
                try:
                    subprocess.Popen([executable], close_fds=True)
                    await asyncio.sleep(3)
                    devices = await self._devices(token)
                    usable = [d for d in devices if not d.get("is_restricted")]
                except OSError:
                    pass
        device = next((d for d in usable if d.get("is_active")), None) or (usable[0] if usable else None)
        if not device:
            return {"success": False, "state": "ERROR", "provider": self.name, "code": "NO_SPOTIFY_PLAYBACK_DEVICE", "message": "No Spotify playback device is available. Open Spotify and start a device, then try again."}
        await spotify_oauth.request("PUT", "/me/player/play", token=token, params={"device_id": device.get("id")}, json={"uris": [track["uri"]]})
        await asyncio.sleep(2)
        current = await self._current(token)
        matches = _norm(current.get("title", "")) == _norm(track.get("name", "")) and _norm(current.get("artist", "")) in {_norm(a) for a in track.get("artists", [])}
        if not current.get("is_playing") or not matches:
            current.update(success=False, code="SPOTIFY_API_NOT_PLAYING", message="Spotify accepted the play request but playback verification did not match the requested track.")
            return current
        current.update(success=True, code="SPOTIFY_API_PLAYING", provider=self.name)
        return current

    async def _current(self, token: str) -> dict[str, Any]:
        data = await spotify_oauth.request("GET", "/me/player", token=token)
        item = data.get("item") or {}
        artists = item.get("artists") or []
        return {"state": "PLAYING" if data.get("is_playing") else "PAUSED", "is_playing": bool(data.get("is_playing")), "device": (data.get("device") or {}).get("name"), "track_id": item.get("id"), "title": item.get("name"), "artist": artists[0].get("name") if artists else None, "provider": self.name}

    async def _control(self, token: str, action: str, volume: int | None) -> dict[str, Any]:
        paths = {"pause": ("PUT", "/me/player/pause"), "stop": ("PUT", "/me/player/pause"), "resume": ("PUT", "/me/player/play"), "next": ("POST", "/me/player/next"), "previous": ("POST", "/me/player/previous"), "volume": ("PUT", "/me/player/volume")}
        method, path = paths[action]
        params = {"volume_percent": int(volume)} if action == "volume" and volume is not None else {}
        await spotify_oauth.request(method, path, token=token, params=params)
        await asyncio.sleep(1)
        return await self._current(token)


class MediaProviderManager(MediaProvider):
    name = "auto"

    def __init__(self):
        self._spotify_provider: SpotifyProvider | None = None
        self._spotify_checked = False

    async def _providers(self) -> list[MediaProvider]:
        native = await WindowsMediaProvider.discover()
        if native:
            return [native]
        if not self._spotify_checked:
            self._spotify_provider = SpotifyProvider.discover()
            self._spotify_checked = True
        return [self._spotify_provider] if self._spotify_provider else []

    async def execute(self, action: str, query: str = "", **kwargs: Any) -> dict[str, Any]:
        providers = await self._providers()
        if not providers:
            return await UnavailableMediaProvider().execute(action, query)
        last_result = None
        for provider in providers:
            result = await provider.execute(action, query, **kwargs)
            last_result = result
            if result.get("success") or result.get("code") not in {"MEDIA_UNAVAILABLE", "PROVIDER_UNAVAILABLE"}:
                return result
        if last_result is not None and action == "current":
            return last_result
        return {"success": False, "state": "ERROR", "provider": self.name,
                "code": "PROVIDER_UNAVAILABLE", "message": "Available media providers could not complete the request."}

    async def status(self) -> dict[str, Any]:
        native = await WindowsMediaProvider.discover()
        spotify_app = resolve_application("spotify")
        vlc_app = resolve_application("vlc")
        return {
            "windows_smtc": {"available": native is not None, "state": "READY" if native else "NO_ACTIVE_SESSION"},
            "spotify": {"installed": bool(spotify_app and installed_executable(spotify_app)), "supported": True},
            "vlc": {"installed": bool(vlc_app and installed_executable(vlc_app)), "supported": False, "reason": "No safe VLC control adapter is configured."},
        }


class MediaControlTool(BaseTool):
    name = "media_control"
    description = "Control or inspect an available local media provider."
    permission = "SAFE"

    def __init__(self, provider: MediaProvider | None = None):
        self.provider = provider or MediaProviderManager()

    async def execute(self, action: str = "current", query: str = "", volume: int | None = None, **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("media_control received unexpected arguments")
        if action not in MEDIA_ACTIONS:
            raise ValueError("Unsupported media action")
        if action == "volume" and volume is not None and not 0 <= int(volume) <= 100:
            raise ValueError("volume must be an integer from 0 to 100")
        return await self.provider.execute(action, query, volume=volume)


def register_media_tools(registry: ToolRegistry) -> ToolRegistry:
    registry.register(MediaControlTool())
    return registry


# Media is kept as a capability-specific view over the same ToolRegistry
# interface; execution still goes through ActionAuthority in the API layer.
media_registry = register_media_tools(ToolRegistry())
