import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from backend.app.core.action_authority import ActionAuthority
from backend.app.config.settings import settings
from backend.app.tools.media_tools import MediaProviderManager, SpotifyError, media_registry, spotify_oauth

router = APIRouter(prefix="/media", tags=["Media"])


@router.get("/status")
async def media_status():
    """Return verified current media state without starting playback."""
    return await ActionAuthority(media_registry).execute("media_control", {"action": "current"})


@router.get("/providers")
async def media_providers():
    result = await MediaProviderManager().status()
    result["spotify"].update(await spotify_oauth.status())
    return result


@router.get("/spotify/status")
async def spotify_status():
    return await spotify_oauth.status()


@router.post("/spotify/connect")
async def spotify_connect_start(request: Request):
    if not spotify_oauth.configured:
        raise HTTPException(status_code=503, detail="Spotify isn't configured yet. Add the backend Spotify OAuth settings.")
    origin = request.headers.get("origin", "").rstrip("/")
    allowed_origins = {*settings.cors_origins, settings.frontend_base_url.rstrip("/")}
    frontend_return_url = origin if origin in allowed_origins else None
    return {"authorization_url": spotify_oauth.authorization_url(frontend_return_url)}


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
