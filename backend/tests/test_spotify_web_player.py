from urllib.parse import parse_qs, urlsplit
from pydantic import SecretStr

from backend.app.config.settings import settings
from backend.app.core.capabilities import Capability, classify_command
from backend.app.tools.media_tools import SpotifyOAuth, spotify_player_runtime


def test_web_playback_oauth_requests_only_player_scopes(monkeypatch):
    monkeypatch.setattr(settings, "spotify_client_id", "client-id")
    monkeypatch.setattr(settings, "spotify_client_secret", SecretStr("secret"))
    params = parse_qs(urlsplit(SpotifyOAuth().authorization_url()).query)
    scopes = set(params["scope"][0].split())
    assert {"streaming", "user-read-email", "user-read-private", "user-read-playback-state", "user-modify-playback-state"} <= scopes


def test_browser_device_runtime_is_ephemeral():
    spotify_player_runtime.clear()
    spotify_player_runtime.register("sdk-device-id", "LEON Player")
    assert spotify_player_runtime.status()["sdk_ready"] is True
    assert spotify_player_runtime.status()["device_id"] == "sdk-device-id"
    spotify_player_runtime.mark_not_ready("sdk-device-id")
    assert spotify_player_runtime.status()["device_id"] is None
    assert spotify_player_runtime.status()["sdk_ready"] is False
    spotify_player_runtime.clear()


def test_hindi_media_commands_route_to_media():
    assert classify_command("Leon Spotify chalao").capability == Capability.MEDIA
    assert classify_command("Gaana pause karo").action == "pause"
    assert classify_command("Agla gaana chalao").action == "next"
    assert classify_command("Abhi kaunsa gaana baj raha hai?").action == "current"

