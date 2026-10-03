import pytest

from backend.app.core.capabilities import Capability, classify_command
from backend.app.tools.media_tools import MediaControlTool, MediaProvider


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
