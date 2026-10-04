import pytest

from backend.app.core.capabilities import Capability, classify_command
from backend.app.tools import media_tools
from backend.app.tools.media_tools import (
    MediaControlTool,
    MediaProvider,
    MediaProviderManager,
    SpotifyProvider,
    WindowsMediaProvider,
    YouTubeMusicProvider,
)


def test_media_routing_variations():
    assert classify_command("put on Blinding Lights").capability == Capability.MEDIA
    assert classify_command("skip").action == "next"
    assert classify_command("what's playing?").action == "current"
    assert classify_command("turn the volume down").action == "volume"


class MockProvider(MediaProvider):
    name = "mock-player"

    async def execute(self, action, query="", **kwargs):
        return {"success": True, "state": "PLAYING", "provider": self.name,
                "action": action, "query": query}


@pytest.mark.anyio
async def test_media_tool_validates_and_delegates():
    tool = MediaControlTool(MockProvider())
    result = await tool.execute("play", "Blinding Lights")
    assert result["provider"] == "mock-player"
    assert result["action"] == "play"
    with pytest.raises(ValueError):
        await tool.execute("volume", volume=101)


@pytest.mark.anyio
async def test_windows_media_discovery_is_disabled_without_opt_in(monkeypatch):
    monkeypatch.setattr(media_tools.settings, "windows_media_enabled", False)

    assert await WindowsMediaProvider.discover() is None


@pytest.mark.anyio
async def test_youtube_music_play_opens_encoded_search(monkeypatch):
    opened = []
    monkeypatch.setattr(media_tools.webbrowser, "open", lambda url, new: opened.append((url, new)) or True)

    result = await YouTubeMusicProvider().execute("play", "Play Here Comes the Sun by The Beatles on YouTube Music")

    assert result["success"] is True
    assert result["provider"] == "youtube_music"
    assert result["state"] == "SEARCH_OPENED"
    assert opened == [
        ("https://music.youtube.com/search?q=Here+Comes+the+Sun+by+The+Beatles", 2)
    ]


@pytest.mark.anyio
async def test_media_manager_honors_explicit_provider_without_local_spotify_app(monkeypatch):
    async def execute(self, action, query="", **kwargs):
        return {"success": True, "provider": self.name, "action": action, "query": query}

    monkeypatch.setattr(SpotifyProvider, "execute", execute)

    result = await MediaProviderManager().execute(
        "play",
        "Play a song on Spotify",
        provider="spotify",
    )

    assert result["success"] is True
    assert result["provider"] == "spotify"
