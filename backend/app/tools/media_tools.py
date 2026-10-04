"""Safe local media control with provider discovery and verification."""
from __future__ import annotations

import os
import subprocess
import asyncio
import json
import re
import secrets
import time
import webbrowser
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import quote_plus, urlencode
import httpx

from .applications import installed_executable, resolve_application
from .base import BaseTool
from .registry import ToolRegistry
from backend.app.config.settings import settings

MEDIA_ACTIONS = {"play", "pause", "resume", "stop", "next", "previous", "current", "volume", "search"}
SPOTIFY_API = "https://api.spotify.com/v1"
SPOTIFY_ACCOUNTS = "https://accounts.spotify.com"
SPOTIFY_SCOPES = "streaming user-read-email user-read-private user-read-playback-state user-modify-playback-state"
SPOTIFY_REQUIRED_SCOPES = frozenset(SPOTIFY_SCOPES.split())
SPOTIFY_VERIFICATION_DELAYS = (0.1, 0.2, 0.3, 0.5, 0.8, 1.0)


class SpotifyError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 503):
        super().__init__(message)
        self.code, self.status_code = code, status_code


class SpotifyPlayerRuntime:
    """Runtime-only state for the browser-created Spotify Connect device.

    Spotify device IDs are ephemeral. This state is intentionally not written
    to the token file or treated as durable account data.
    """

    def __init__(self) -> None:
        self.device_id: str | None = None
        self.device_name = "LEON Player"
        self.sdk_loaded = False
        self.sdk_connected = False
        self.sdk_ready = False
        self.last_error_code: str | None = None
        self.last_error: str | None = None
        self.last_seen = 0.0

    def register(self, device_id: str, device_name: str = "LEON Player") -> None:
        self.device_id = device_id.strip()
        self.device_name = device_name.strip() or "LEON Player"
        self.sdk_loaded = True
        self.sdk_connected = True
        self.sdk_ready = True
        self.last_seen = time.time()
        self.last_error_code = None
        self.last_error = None

    def mark_not_ready(self, device_id: str | None = None) -> None:
        if device_id and self.device_id and device_id != self.device_id:
            return
        self.sdk_ready = False
        self.sdk_connected = False
        self.device_id = None
        self.last_seen = 0.0

    def clear(self) -> None:
        self.device_id = None
        self.sdk_connected = False
        self.sdk_ready = False
        self.last_seen = 0.0
        self.last_error_code = None
        self.last_error = None

    def error(self, code: str, message: str) -> None:
        self.sdk_loaded = True
        self.last_error_code = code
        self.last_error = message
        self.sdk_ready = False

    def status(self) -> dict[str, Any]:
        if self.sdk_ready and self.last_seen and time.time() - self.last_seen > 15:
            self.mark_not_ready(self.device_id)
        return {
            "sdk_loaded": self.sdk_loaded,
            "sdk_connected": self.sdk_connected,
            "sdk_ready": self.sdk_ready,
            "device_id": self.device_id,
            "device_name": self.device_name if self.device_id else None,
            "device_available": self.sdk_ready and bool(self.device_id),
            "last_error_code": self.last_error_code,
            "last_error": self.last_error,
        }


spotify_player_runtime = SpotifyPlayerRuntime()


def _norm(value: str) -> str:
    return " ".join((value or "").casefold().replace("’", "'").split())


class SpotifyOAuth:
    def __init__(self) -> None:
        self._state: str | None = None
        self._frontend_return_url = settings.frontend_base_url.rstrip("/")
        self._lock = asyncio.Lock()

    async def _http_call(self, method: str, url: str, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            request_method = getattr(client, method.lower(), None)
            if callable(request_method):
                return await request_method(url, **kwargs)
            return await client.request(method, url, **kwargs)

    @property
    def configured(self) -> bool:
        return bool(settings.spotify_client_id.strip() and settings.spotify_client_secret.get_secret_value().strip())

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(settings.spotify_token_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
            return {}

    @staticmethod
    def missing_scopes(token: dict[str, Any]) -> list[str]:
        granted = set(str(token.get("scope") or "").split())
        return sorted(SPOTIFY_REQUIRED_SCOPES - granted)

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
        params = {"client_id": settings.spotify_client_id.strip(), "response_type": "code", "redirect_uri": settings.spotify_redirect_uri, "scope": SPOTIFY_SCOPES, "state": self._state, "show_dialog": "true"}
        return f"{SPOTIFY_ACCOUNTS}/authorize?{urlencode(params)}"

    def frontend_return_url(self, state: str) -> str:
        if self._state and secrets.compare_digest(self._state, state):
            return self._frontend_return_url
        return settings.frontend_base_url.rstrip("/")

    async def callback(self, code: str, state: str) -> None:
        if not self._state or not secrets.compare_digest(self._state, state):
            raise ValueError("Invalid Spotify OAuth state.")
        response = await self._http_call(
            "POST",
            f"{SPOTIFY_ACCOUNTS}/api/token",
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": settings.spotify_redirect_uri},
            auth=(settings.spotify_client_id.strip(), settings.spotify_client_secret.get_secret_value().strip()),
        )
        response.raise_for_status()
        token = response.json()
        if not token.get("access_token"):
            raise SpotifyError("SPOTIFY_TOKEN_INVALID", "Spotify token exchange returned no access token.", 502)
        token["expires_at"] = time.time() + int(token.get("expires_in", 3600))
        self._write(token)
        self._state = None

    async def access_token(self, *, force_refresh: bool = False) -> str | None:
        if not self.configured:
            return None
        token = self._read()
        if not force_refresh and token.get("access_token") and float(token.get("expires_at", 0)) > time.time() + 30:
            return str(token["access_token"])
        refresh = token.get("refresh_token")
        if not refresh:
            return None
        async with self._lock:
            token = self._read()
            if not force_refresh and token.get("access_token") and float(token.get("expires_at", 0)) > time.time() + 30:
                return str(token["access_token"])
            try:
                response = await self._http_call(
                    "POST",
                    f"{SPOTIFY_ACCOUNTS}/api/token",
                    data={"grant_type": "refresh_token", "refresh_token": refresh},
                    auth=(settings.spotify_client_id.strip(), settings.spotify_client_secret.get_secret_value().strip()),
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise SpotifyError("SPOTIFY_AUTH_REQUIRED", "Spotify authorization could not be refreshed; reconnect Spotify.", 401) from exc
            refreshed = response.json()
            refreshed.setdefault("refresh_token", refresh)
            refreshed.setdefault("scope", token.get("scope", ""))
            refreshed["expires_at"] = time.time() + int(refreshed.get("expires_in", 3600))
            self._write(refreshed)
            access_token = refreshed.get("access_token")
            return str(access_token) if access_token else None

    async def request(self, method: str, path: str, *, token: str, _retry_auth: bool = True, **kwargs: Any) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.request(method, f"{SPOTIFY_API}{path}", headers={"Authorization": f"Bearer {token}"}, **kwargs)
        if response.status_code == 204:
            return {}
        if response.status_code == 401:
            # A token can expire between the proactive check and the Web API
            # request. Refresh once only when the active bearer token matches the
            # stored session; direct requests using a one-off token should surface
            # the original HTTP status instead of re-triggering OAuth.
            stored = self._read()
            if _retry_auth and stored.get("refresh_token") and str(stored.get("access_token") or "") == str(token):
                refreshed = await self.access_token(force_refresh=True)
                if refreshed and refreshed != token:
                    return await self.request(method, path, token=refreshed, _retry_auth=False, **kwargs)
            raise SpotifyError("SPOTIFY_AUTH_REQUIRED", "Spotify authorization expired; reconnect Spotify.", 401)
        if response.status_code == 403:
            raise SpotifyError("SPOTIFY_PLAYBACK_FORBIDDEN", "Spotify playback control requires Premium and playback permission.", 403)
        if response.status_code == 429:
            retry_after = getattr(response, "headers", {}).get("Retry-After", "")
            message = "Spotify is rate limiting requests. Try again shortly."
            if retry_after.isdigit():
                message = f"Spotify is rate limiting requests. Retry after {retry_after} seconds."
            raise SpotifyError("SPOTIFY_RATE_LIMITED", message, 429)
        response.raise_for_status()
        return response.json() if response.content else {}

    async def status(self) -> dict[str, Any]:
        token_path = settings.spotify_token_path
        token_file_exists = token_path.is_file()
        stored = self._read()
        runtime = spotify_player_runtime.status()
        if not self.configured:
            # Preserve the small legacy response for callers that only need
            # the setup decision. Configured responses contain the complete
            # runtime state below.
            return {"configured": False, "authenticated": False, "requires_auth": True, "error_code": "SPOTIFY_NOT_CONFIGURED"}
        if not stored:
            return {
                "configured": True,
                "authenticated": False,
                "requires_auth": True,
                "state": "AUTH_REQUIRED",
                "premium_available": None,
                "playback_available": False,
                "error_code": "SPOTIFY_TOKEN_MISSING" if not token_file_exists else "SPOTIFY_TOKEN_INVALID",
                **runtime,
            }
        try:
            token = await self.access_token()
        except (httpx.HTTPError, SpotifyError, ValueError, TypeError, OSError):
            return {
                "configured": True,
                "authenticated": False,
                "requires_auth": True,
                "state": "AUTH_REQUIRED",
                "premium_available": None,
                "playback_available": False,
                "error_code": "SPOTIFY_TOKEN_REFRESH_FAILED",
                **runtime,
            }
        result: dict[str, Any] = {
            "configured": True,
            "authenticated": bool(token),
            "requires_auth": not bool(token),
            "state": "AUTHENTICATED" if token else "AUTH_REQUIRED",
            "premium_available": None,
            "playback_available": False,
            **runtime,
        }
        missing_scopes = self.missing_scopes(stored)
        if missing_scopes:
            result.update(error_code="SPOTIFY_SCOPE_REQUIRED", missing_scopes=missing_scopes)
        if not token:
            result["error_code"] = "SPOTIFY_TOKEN_INVALID"
            return result
        try:
            devices = await self.request("GET", "/me/player/devices", token=token)
            account = await self.request("GET", "/me", token=token)
            playback = await self.request("GET", "/me/player", token=token)
            available = [device for device in devices.get("devices", []) if not device.get("is_restricted")]
            current = playback.get("device") or next((device for device in available if device.get("is_active")), None)
            item = playback.get("item") or {}
            artists = item.get("artists") or []
            album = item.get("album") or {}
            premium = str(account.get("product") or "").casefold() == "premium"
            result.update(
                account_authorized=True,
                account_name=account.get("display_name") or account.get("id"),
                premium_available=premium,
                state="ACCOUNT_UNAVAILABLE" if not premium else ("PLAYBACK_READY" if runtime.get("sdk_ready") else "AUTHENTICATED"),
                devices_available=len(available),
                remote_devices=available,
                current_device_id=current.get("id") if current else None,
                current_device_name=current.get("name") if current else None,
                playback_available=bool(playback),
                is_playing=bool(playback.get("is_playing")),
                current_track=item.get("name") or None,
                current_artist=artists[0].get("name") if artists else None,
                current_album=album.get("name") or None,
                album_art_url=(album.get("images") or [{}])[0].get("url") if album.get("images") else None,
                progress_ms=playback.get("progress_ms"),
            )
            if missing_scopes:
                result.update(
                    state="AUTH_REQUIRED",
                    playback_available=False,
                    error_code="SPOTIFY_SCOPE_REQUIRED",
                    missing_scopes=missing_scopes,
                )
        except SpotifyError as exc:
            result.update(
                account_authorized=exc.status_code != 401,
                error_code="SPOTIFY_TOKEN_INVALID" if exc.status_code == 401 else exc.code,
            )
            if exc.status_code == 401:
                result.update(authenticated=False, requires_auth=True, state="AUTH_REQUIRED")
            elif exc.status_code == 403:
                result["state"] = "ACCOUNT_UNAVAILABLE"
        except httpx.HTTPError:
            result.update(account_authorized=False, error_code="SPOTIFY_STATUS_UNAVAILABLE")
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
        if os.name != "nt" or not settings.windows_media_enabled:
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
        return cls() if spotify_oauth.configured else None

    async def execute(self, action: str, query: str = "", **kwargs: Any) -> dict[str, Any]:
        try:
            token = await spotify_oauth.access_token()
        except SpotifyError as exc:
            return {"success": False, "state": "AUTH_REQUIRED", "provider": self.name, "code": exc.code, "message": str(exc)}
        if not token:
            return {"success": False, "state": "UNAVAILABLE", "provider": self.name, "code": "SPOTIFY_AUTH_REQUIRED", "message": "Connect Spotify before controlling playback."}
        try:
            if action == "search":
                return {"success": True, "state": "SEARCHED", "provider": self.name, "tracks": await self._search(token, query)}
            if action == "play":
                return await self._play(token, query, **kwargs)
            if action in {"pause", "resume", "stop", "next", "previous", "volume"}:
                return await self._control(token, action, kwargs.get("volume"), **kwargs)
            if action == "current":
                return await self._current(token)
            return {"success": False, "state": "ERROR", "provider": self.name, "code": "UNSUPPORTED_OPERATION", "message": "Unsupported Spotify action."}
        except SpotifyError as exc:
            return {"success": False, "state": "ERROR", "provider": self.name, "code": exc.code, "message": str(exc)}
        except httpx.HTTPError as exc:
            return {"success": False, "state": "ERROR", "provider": self.name, "code": "SPOTIFY_UNAVAILABLE", "message": f"Spotify is unavailable: {exc}"}

    async def _search(self, token: str, query: str) -> list[dict[str, Any]]:
        data = await spotify_oauth.request("GET", "/search", token=token, params={"q": query, "type": "track", "limit": 10})
        tracks = data.get("tracks", {}).get("items", [])
        return [{"id": item.get("id"), "uri": item.get("uri"), "name": item.get("name"),
                 "artists": [a.get("name") for a in item.get("artists", [])],
                 "album": (item.get("album") or {}).get("name"),
                 "album_art_url": ((item.get("album") or {}).get("images") or [{}])[0].get("url")
                 if (item.get("album") or {}).get("images") else None} for item in tracks]

    async def _resolve_track(self, token: str, query: str) -> dict[str, Any] | None:
        cleaned = re.sub(r"^\s*(?:play|start|put on|listen to)\s+", "", query, flags=re.IGNORECASE)
        cleaned = re.sub(r"^\s*(?:leon[,:]?\s*)?(?:spotify\s+chalao|gaana\s+chalao)\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+ka\s+(?:ye\s+)?song\s+play\s+karo\s*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^\s*(?:leon[,:]?\s*)?(.+?)\s+ka\s+(?:ye\s+)?song\s+play\s+karo\s*[.!?]*$", r"\1", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+(?:on\s+)?spotify\s*[.!?]*$", "", cleaned, flags=re.IGNORECASE)
        title, _, artist = cleaned.partition(" by ")
        search_query = f'track:"{title.strip()}"' + (f' artist:"{artist.strip()}"' if artist.strip() else "")
        tracks = await self._search(token, search_query)
        wanted_title, wanted_artist = _norm(title), _norm(artist)
        exact = [t for t in tracks if _norm(t.get("name", "")) == wanted_title and (not wanted_artist or any(_norm(a) == wanted_artist for a in t.get("artists", [])))]
        if exact:
            return exact[0] if len(exact) == 1 else {**exact[0], "_ambiguous": True}
        if tracks:
            ranked = sorted(
                tracks,
                key=lambda track: (
                    _norm(track.get("name", "")) == wanted_title,
                    bool(wanted_artist and any(_norm(a) == wanted_artist for a in track.get("artists", []))),
                ),
                reverse=True,
            )
            if len(ranked) > 1 and (
                _norm(ranked[0].get("name", "")) == _norm(ranked[1].get("name", ""))
                and not wanted_artist
            ):
                return {**ranked[0], "_ambiguous": True}
            return ranked[0]
        return None

    async def _devices(self, token: str) -> list[dict[str, Any]]:
        return (await spotify_oauth.request("GET", "/me/player/devices", token=token)).get("devices", [])

    async def _poll_current(self, token: str, predicate) -> dict[str, Any]:
        current: dict[str, Any] = {}
        for index, delay in enumerate(SPOTIFY_VERIFICATION_DELAYS):
            if index:
                await asyncio.sleep(delay)
            current = await self._current(token)
            if predicate(current):
                return current
        return current

    async def _play(self, token: str, query: str, **kwargs: Any) -> dict[str, Any]:
        track = await self._resolve_track(token, query)
        if not track or not track.get("uri"):
            return {"success": False, "state": "ERROR", "provider": self.name, "code": "SPOTIFY_TRACK_NOT_FOUND", "message": "Spotify could not find that track."}
        if track.get("_ambiguous"):
            return {"success": False, "state": "ERROR", "provider": self.name, "code": "AMBIGUOUS_TRACK", "message": "Spotify found multiple matching tracks. Include the exact track title and artist."}
        devices = await self._devices(token)
        usable = [d for d in devices if not d.get("is_restricted")]
        requested_device_id = kwargs.get("device_id")
        runtime_status = spotify_player_runtime.status()
        leon_device_id = runtime_status["device_id"] if runtime_status["sdk_ready"] else None
        target_id = requested_device_id or leon_device_id
        device = next((d for d in usable if d.get("id") == target_id), None) if target_id else None
        if not target_id:
            # Remote Spotify devices remain supported when LEON has not been
            # enabled; LEON is preferred automatically once its SDK device is
            # ready.
            device = next((d for d in usable if d.get("is_active")), None) or (usable[0] if usable else None)
        # The SDK ready event is authoritative even while Spotify is still
        # refreshing its device list. Never silently fall back to desktop or
        # phone playback when LEON is not ready.
        if target_id and target_id == leon_device_id and not device:
            device = {"id": target_id, "name": spotify_player_runtime.device_name, "is_restricted": False}
        if not device:
            return {"success": False, "state": "NO_DEVICE", "provider": self.name, "code": "NO_SPOTIFY_PLAYBACK_DEVICE", "message": "LEON Player is not ready. Open Media, click Enable Player, and wait for the Spotify device to become ready."}
        active = next((d for d in usable if d.get("is_active")), None)
        if leon_device_id and active and active.get("id") != leon_device_id:
            await spotify_oauth.request("PUT", "/me/player", token=token, json={"device_ids": [leon_device_id], "play": True})
        await spotify_oauth.request("PUT", "/me/player/play", token=token, params={"device_id": device.get("id")}, json={"uris": [track["uri"]]})
        wanted_artists = {_norm(a) for a in track.get("artists", [])}
        current = await self._poll_current(
            token,
            lambda state: state.get("device_id") == device.get("id")
            and state.get("is_playing")
            and _norm(state.get("title", "")) == _norm(track.get("name", ""))
            and _norm(state.get("artist", "")) in wanted_artists,
        )
        if current.get("is_playing") and _norm(current.get("title", "")) == _norm(track.get("name", "")):
            current.update(success=True, code="SPOTIFY_API_PLAYING", provider=self.name)
            return current
        current.update(success=False, code="VERIFICATION_TIMEOUT", message="Spotify accepted the play request but LEON could not verify the requested track playing.")
        return current

    async def _current(self, token: str) -> dict[str, Any]:
        data = await spotify_oauth.request("GET", "/me/player", token=token)
        if not data:
            return {"success": False, "state": "NO_DEVICE", "is_playing": False, "device_id": None,
                    "device": None, "track_id": None, "title": None, "artist": None, "album": None,
                    "album_art_url": None, "progress_ms": None, "provider": self.name, "code": "NO_DEVICE"}
        item = data.get("item") or {}
        artists = item.get("artists") or []
        album = item.get("album") or {}
        device = data.get("device") or {}
        return {"success": True, "state": "PLAYING" if data.get("is_playing") else "PAUSED",
                "is_playing": bool(data.get("is_playing")), "device_id": device.get("id"),
                "device": device.get("name"), "track_id": item.get("id"), "title": item.get("name"),
                "artist": artists[0].get("name") if artists else None, "album": album.get("name"),
                "album_art_url": (album.get("images") or [{}])[0].get("url") if album.get("images") else None,
                "progress_ms": data.get("progress_ms"), "duration_ms": item.get("duration_ms"),
                "provider": self.name}

    async def _control(self, token: str, action: str, volume: int | None, **kwargs: Any) -> dict[str, Any]:
        paths = {"pause": ("PUT", "/me/player/pause"), "stop": ("PUT", "/me/player/pause"), "resume": ("PUT", "/me/player/play"), "next": ("POST", "/me/player/next"), "previous": ("POST", "/me/player/previous"), "volume": ("PUT", "/me/player/volume")}
        method, path = paths[action]
        params = {"volume_percent": int(volume)} if action == "volume" and volume is not None else {}
        runtime_status = spotify_player_runtime.status()
        target_id = kwargs.get("device_id") or (runtime_status["device_id"] if runtime_status["sdk_ready"] else None)
        if target_id and action not in {"volume"}:
            params["device_id"] = target_id
        before = await self._current(token)
        await spotify_oauth.request(method, path, token=token, params=params)
        if action in {"pause", "stop"}:
            current = await self._poll_current(token, lambda state: state.get("is_playing") is False)
            expected = current.get("is_playing") is False
        elif action == "resume":
            current = await self._poll_current(token, lambda state: state.get("is_playing") is True)
            expected = current.get("is_playing") is True
        elif action in {"next", "previous"}:
            previous_id = before.get("track_id")
            current = await self._poll_current(token, lambda state: bool(state.get("track_id")) and state.get("track_id") != previous_id)
            expected = current.get("track_id") != previous_id
        else:
            current = await self._current(token)
            expected = current.get("success", False)
        current.update(success=bool(expected), code="SPOTIFY_API_VERIFIED" if expected else "VERIFICATION_TIMEOUT")
        if not expected:
            current["message"] = "Spotify accepted the command but LEON could not verify the resulting playback state."
        return current


class YouTubeMusicProvider(MediaProvider):
    name = "youtube_music"

    async def execute(self, action: str, query: str = "", **kwargs: Any) -> dict[str, Any]:
        if action in {"play", "search"}:
            cleaned = re.sub(
                r"^\s*(?:play|start|put on|listen to|search for)\s+",
                "",
                query,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(
                r"\s+(?:on\s+)?(?:youtube\s*music|yt\s*music|ytmusic)\s*[.!?]*$",
                "",
                cleaned,
                flags=re.IGNORECASE,
            ).strip()
            url = (
                "https://music.youtube.com/"
                if not cleaned
                else f"https://music.youtube.com/search?q={quote_plus(cleaned)}"
            )
            opened = webbrowser.open(url, new=2)
            if not opened:
                return {
                    "success": False,
                    "state": "ERROR",
                    "provider": self.name,
                    "code": "YOUTUBE_MUSIC_BROWSER_UNAVAILABLE",
                    "message": "Could not open YouTube Music in the default browser.",
                }
            message = (
                f"Opened YouTube Music search for {cleaned}. Choose a result to start playback."
                if cleaned
                else "Opened YouTube Music."
            )
            return {
                "success": True,
                "state": "SEARCH_OPENED" if cleaned else "OPENED",
                "provider": self.name,
                "url": url,
                "message": message,
            }

        native = await WindowsMediaProvider.discover()
        if native is None:
            return {
                "success": False,
                "state": "UNAVAILABLE",
                "provider": self.name,
                "code": "YOUTUBE_MUSIC_CONTROLS_UNAVAILABLE",
                "message": "Open YouTube Music and enable Windows media controls to control its playback by voice.",
            }
        session = native.manager.get_current_session()
        app_id = str(getattr(session, "source_app_user_model_id", "") or "").casefold()
        if not any(browser in app_id for browser in ("chrome", "msedge", "firefox", "brave", "opera")):
            return {
                "success": False,
                "state": "UNAVAILABLE",
                "provider": self.name,
                "code": "YOUTUBE_MUSIC_NOT_ACTIVE",
                "message": "No active browser media session was found for YouTube Music.",
            }
        result = await native.execute(action, query, **kwargs)
        result["provider"] = self.name
        return result


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
        requested_provider = kwargs.pop("provider", None)
        if requested_provider == "spotify":
            return await SpotifyProvider().execute(action, query, **kwargs)
        if requested_provider == "youtube_music":
            return await YouTubeMusicProvider().execute(action, query, **kwargs)
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
            "youtube_music": {"supported": True, "mode": "browser_search", "playback_controls": native is not None},
            "vlc": {"installed": bool(vlc_app and installed_executable(vlc_app)), "supported": False, "reason": "No safe VLC control adapter is configured."},
        }


class MediaControlTool(BaseTool):
    name = "media_control"
    description = "Control or inspect an available local media provider."
    permission = "SAFE"

    def __init__(self, provider: MediaProvider | None = None):
        self.provider = provider or MediaProviderManager()

    async def execute(
        self,
        action: str = "current",
        query: str = "",
        volume: int | None = None,
        provider: str | None = None,
        device_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if kwargs:
            raise ValueError("media_control received unexpected arguments")
        if action not in MEDIA_ACTIONS:
            raise ValueError("Unsupported media action")
        if action == "volume" and volume is not None and not 0 <= int(volume) <= 100:
            raise ValueError("volume must be an integer from 0 to 100")
        if provider not in {None, "spotify", "youtube_music"}:
            raise ValueError("Unsupported media provider")
        return await self.provider.execute(action, query, volume=volume, provider=provider, device_id=device_id)


def register_media_tools(registry: ToolRegistry) -> ToolRegistry:
    registry.register(MediaControlTool())
    return registry


# Media is kept as a capability-specific view over the same ToolRegistry
# interface; execution still goes through ActionAuthority in the API layer.
media_registry = register_media_tools(ToolRegistry())
