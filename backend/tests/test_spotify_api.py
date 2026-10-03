import asyncio
from pathlib import Path

import pytest
from pydantic import SecretStr

from backend.app.config.settings import Settings, settings
from backend.app.tools import media_tools
from backend.app.tools.media_tools import SpotifyError, SpotifyProvider, SpotifyOAuth


def test_development_default_frontend_base_url_matches_current_local_ui():
    dev_settings = Settings(_env_file=None, app_env="development")
    assert dev_settings.frontend_base_url == "http://127.0.0.1:5174"


def test_spotify_oauth_status_is_non_secret_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "spotify_client_id", "")
    monkeypatch.setattr(settings, "spotify_token_path", Path(tmp_path) / "tokens.json")
    result = asyncio.run(SpotifyOAuth().status())
    assert result == {"configured": False, "authenticated": False, "requires_auth": True, "error_code": "SPOTIFY_NOT_CONFIGURED"}


def test_spotify_missing_token_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "spotify_client_id", "client")
    monkeypatch.setattr(settings, "spotify_client_secret", SecretStr("secret"))
    monkeypatch.setattr(settings, "spotify_token_path", Path(tmp_path) / "tokens.json")
    result = asyncio.run(SpotifyOAuth().status())
    assert result["authenticated"] is False
    assert result["error_code"] == "SPOTIFY_TOKEN_MISSING"


def test_spotify_token_write_loads_across_instances(tmp_path, monkeypatch):
    path = Path(tmp_path) / "nested" / "tokens.json"
    monkeypatch.setattr(settings, "spotify_token_path", path)
    writer = SpotifyOAuth()
    writer._write({"access_token": "safe-test-token", "refresh_token": "refresh", "expires_at": 9e9})
    assert path.is_file()
    assert SpotifyOAuth()._read()["access_token"] == "safe-test-token"


def test_spotify_callback_persists_exchanged_token(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "spotify_client_id", "client")
    monkeypatch.setattr(settings, "spotify_client_secret", SecretStr("secret"))
    monkeypatch.setattr(settings, "spotify_token_path", Path(tmp_path) / "tokens.json")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(media_tools.httpx, "AsyncClient", lambda **kwargs: Client())
    oauth = SpotifyOAuth()
    url = oauth.authorization_url()
    state = url.split("state=", 1)[1]
    asyncio.run(oauth.callback("code", state))
    saved = SpotifyOAuth()._read()
    assert saved["access_token"] == "access"
    assert saved["refresh_token"] == "refresh"
    assert saved["expires_at"] > 0


def test_track_resolution_prefers_exact_title_and_artist(monkeypatch):
    provider = SpotifyProvider()
    async def search(_token, _query):
        return [
            {"id": "wrong", "uri": "spotify:track:wrong", "name": "I Can't Let You Go", "artists": ["Other"]},
            {"id": "right", "uri": "spotify:track:right", "name": "I Can't Let You Go", "artists": ["K3NT4"]},
        ]
    monkeypatch.setattr(provider, "_search", search)
    result = asyncio.run(provider._resolve_track("token", "Play I Can't Let You Go by K3NT4"))
    assert result["id"] == "right"


def test_no_spotify_device_is_explicit(monkeypatch):
    provider = SpotifyProvider()
    monkeypatch.setattr(media_tools, "installed_executable", lambda *_: None)
    monkeypatch.setattr(provider, "_resolve_track", lambda *_: asyncio.sleep(0, result={"uri": "spotify:track:1", "name": "Track", "artists": ["Artist"]}))
    monkeypatch.setattr(provider, "_devices", lambda *_: asyncio.sleep(0, result=[]))
    result = asyncio.run(provider._play("token", "Track by Artist"))
    assert result["code"] == "NO_SPOTIFY_PLAYBACK_DEVICE"
    assert result["success"] is False


def test_spotify_http_statuses_are_classified(monkeypatch):
    class Response:
        content = b"{}"
        def __init__(self, status): self.status_code = status
        def raise_for_status(self): raise RuntimeError("unexpected")

    class Client:
        def __init__(self, response): self.response = response
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def request(self, *args, **kwargs): return self.response

    for status, code in [(401, "SPOTIFY_AUTH_REQUIRED"), (403, "SPOTIFY_PLAYBACK_FORBIDDEN"), (429, "SPOTIFY_RATE_LIMITED")]:
        monkeypatch.setattr(media_tools.httpx, "AsyncClient", lambda **kwargs: Client(Response(status)))
        with pytest.raises(SpotifyError, match="Spotify") as error:
            asyncio.run(media_tools.spotify_oauth.request("GET", "/me/player", token="secret"))
        assert error.value.code == code
