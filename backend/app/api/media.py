import httpx
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from backend.app.core.action_authority import ActionAuthority
from backend.app.config.settings import settings
from backend.app.tools.media_tools import MediaProviderManager, SpotifyError, media_registry, spotify_oauth, spotify_player_runtime

router = APIRouter(prefix="/media", tags=["Media"])


class SpotifyDeviceRegistration(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    device_name: str = Field(default="LEON Player", max_length=120)


class SpotifyDeviceUnavailable(BaseModel):
    device_id: str | None = Field(default=None, max_length=128)


@router.get("/status")
async def media_status():
    """Return verified current media state without starting playback."""
    try:
        return await ActionAuthority(media_registry).execute("media_control", {"action": "current"})
    except (PermissionError, ValueError, OSError, RuntimeError):
        return {
            "success": False,
            "state": "UNAVAILABLE",
            "message": "Media status is unavailable.",
        }


@router.get("/providers")
async def media_providers():
    result = await MediaProviderManager().status()
    result["spotify"].update(await spotify_oauth.status())
    return result


@router.get("/spotify/status")
async def spotify_status():
    return await spotify_oauth.status()


@router.get("/spotify/token")
async def spotify_token():
    """Return a short-lived SDK token; refresh tokens never leave the backend."""
    if not spotify_oauth.configured:
        raise HTTPException(status_code=503, detail={"code": "SPOTIFY_NOT_CONFIGURED", "message": "Spotify is not configured on the backend."})
    try:
        token = await spotify_oauth.access_token()
    except (SpotifyError, httpx.HTTPError, OSError, ValueError, TypeError):
        token = None
    if not token:
        raise HTTPException(status_code=401, detail={"code": "SPOTIFY_AUTH_REQUIRED", "message": "Connect Spotify again to enable the LEON Player."})
    missing_scopes = spotify_oauth.missing_scopes(spotify_oauth._read())
    if missing_scopes:
        raise HTTPException(status_code=403, detail={
            "code": "SPOTIFY_SCOPE_REQUIRED",
            "message": "Spotify authorization is missing Web Playback permissions. Reauthorize Spotify to enable the LEON Player.",
            "missing_scopes": missing_scopes,
        })
    return {"access_token": token}


@router.post("/spotify/device")
async def spotify_device_register(payload: SpotifyDeviceRegistration):
    spotify_player_runtime.register(payload.device_id, payload.device_name)
    return {"registered": True, **spotify_player_runtime.status()}


@router.delete("/spotify/device")
async def spotify_device_clear(payload: SpotifyDeviceUnavailable | None = None):
    spotify_player_runtime.mark_not_ready(payload.device_id if payload else None)
    return {"registered": False, **spotify_player_runtime.status()}


@router.post("/spotify/connect")
async def spotify_connect_start(request: Request):
    if not spotify_oauth.configured:
        raise HTTPException(status_code=503, detail="Spotify isn't configured yet. Add the backend Spotify OAuth settings.")
    origin = request.headers.get("origin", "").rstrip("/")
    allowed_origins = {*settings.cors_origins, settings.frontend_base_url.rstrip("/")}
    frontend_return_url = origin if origin in allowed_origins else None
    return {"authorization_url": spotify_oauth.authorization_url(frontend_return_url)}


@router.get("/spotify/diagnostic")
async def spotify_diagnostic():
    """Expose non-secret Spotify OAuth wiring details during local development."""
    if settings.app_env.strip().lower() not in {"dev", "development", "local"}:
        raise HTTPException(status_code=404, detail="Not found")
    redirect_uri = settings.spotify_redirect_uri
    redirect_parts = urlsplit(redirect_uri)
    backend_base_url = f"{redirect_parts.scheme}://{redirect_parts.netloc}"
    return {
        "configured_redirect_uri": redirect_uri,
        "actual_authorize_redirect_uri": redirect_uri,
        "frontend_base_url": settings.frontend_base_url.rstrip("/"),
        "backend_base_url": backend_base_url,
    }


@router.get("/spotify/connect")
async def spotify_connect():
    if not spotify_oauth.configured:
        raise HTTPException(status_code=503, detail="Spotify OAuth is not configured on the backend.")
    return RedirectResponse(spotify_oauth.authorization_url())


@router.get("/spotify/callback")
async def spotify_callback(code: str = Query(""), state: str = Query(""), error: str = Query("")):
    frontend_url = spotify_oauth.frontend_return_url(state)
    if error:
        return RedirectResponse(f"{frontend_url}/?spotify=error")
    try:
        await spotify_oauth.callback(code, state)
    except (ValueError, SpotifyError, httpx.HTTPError, OSError):
        return RedirectResponse(f"{frontend_url}/?spotify=error")
    return RedirectResponse(f"{frontend_url}/?spotify=connected")


@router.delete("/spotify/disconnect")
async def spotify_disconnect():
    spotify_oauth.disconnect()
    return {"authenticated": False, "requires_auth": True}
