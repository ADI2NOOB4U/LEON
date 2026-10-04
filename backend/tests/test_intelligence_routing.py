import pytest

from backend.app.api.command import CommandRequest, command
from backend.app.intelligence import intelligence_core


@pytest.mark.parametrize(
    ("message", "route", "intent", "permission"),
    [
        ("hello", "chat.general", "chat.general", "SAFE"),
        ("what time is it?", "system.datetime", "datetime.current", "SAFE"),
        ("what's the weather in London?", "weather.current", "weather.current", "SAFE"),
        ("what's on my screen?", "screen.local", "screen.analyze", "SAFE"),
        ("remember that my project is LEON", "memory.local", "memory.store", "SAFE"),
        ("play a song", "media.spotify", "media.play", "CONFIRM"),
        ("play Here Comes the Sun on YouTube Music", "media.spotify", "media.play", "CONFIRM"),
        ("open VS Code", "desktop.applications", "desktop.open", "CONFIRM"),
        ("search the latest NVIDIA news", "research.current", "research.current", "SAFE"),
        ("send an email to person@example.com subject Hello body Test message", "email.local", "email.send", "CONFIRM"),
    ],
)
def test_core_routes_representative_user_requests(message, route, intent, permission):
    decision = intelligence_core.route(message)

    assert decision.route == route
    assert decision.intent.name == intent
    assert decision.permission == permission


@pytest.mark.anyio
async def test_weather_without_location_is_truthful_clarification(monkeypatch):
    async def unexpected_weather_call(location):
        raise AssertionError(f"weather lookup should not run for {location!r}")

    monkeypatch.setattr("backend.app.api.command.get_current_weather", unexpected_weather_call)
    result = await command(CommandRequest(message="what's the weather?"))

    assert result["type"] == "clarification"
    assert result["verified"] is False


@pytest.mark.anyio
async def test_email_requires_confirmation_before_provider_execution():
    result = await command(CommandRequest(message="send an email to person@example.com subject Hello body Test message"))

    assert result["type"] == "confirmation_required"
    assert result["email"]["to"] == "person@example.com"


@pytest.mark.anyio
async def test_command_selects_youtube_music_provider(monkeypatch):
    calls = {}

    class FakeAuthority:
        def __init__(self, registry):
            pass

        async def execute(self, tool_name, arguments):
            calls.update(tool_name=tool_name, arguments=arguments)
            return {
                "success": True,
                "state": "SEARCH_OPENED",
                "provider": "youtube_music",
                "message": "Opened YouTube Music search.",
            }

    monkeypatch.setattr("backend.app.api.command.ActionAuthority", FakeAuthority)

    result = await command(
        CommandRequest(
            message="play Here Comes the Sun on YouTube Music",
            confirmed=True,
        )
    )

    assert calls["tool_name"] == "media_control"
    assert calls["arguments"]["provider"] == "youtube_music"
    assert result["type"] == "action"
    assert result["verified"] is True
