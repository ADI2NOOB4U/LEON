import pytest

from backend.app.core.capabilities import Capability, classify_command
from backend.app.core.action_authority import ActionAuthority
from backend.app.core.interpreter import LeonInterpreter
from backend.app.security.permissions import PermissionManager
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


def test_deterministic_capability_fast_paths():
    assert classify_command("open VS Code").capability == Capability.SYSTEM
    assert classify_command("pause").action == "pause"
    assert classify_command("what's playing?").action == "current"
    assert classify_command("read what's on my screen").capability == Capability.OCR
    assert classify_command("search the latest NVIDIA news").capability == Capability.RESEARCH
    assert classify_command("create a file called test.txt").requires_confirmation


@pytest.mark.anyio
async def test_interpreter_preserves_deterministic_media_capability():
    interpreter = LeonInterpreter()

    async def unexpected_model_call(*args, **kwargs):
        raise AssertionError("deterministic media commands must not be model-classified")

    interpreter.router.chat = unexpected_model_call
    result = await interpreter.interpret("Play I Can't Let You Go by K3NT4")

    assert result.capability == Capability.MEDIA.value
    assert result.action == "play"
    assert result.intent == "task"


@pytest.mark.anyio
@pytest.mark.parametrize("message", ["hello", "what are you?"])
async def test_interpreter_does_not_model_classify_basic_chat(message):
    interpreter = LeonInterpreter()

    async def unexpected_model_call(*args, **kwargs):
        raise AssertionError("basic conversation must not be model-classified")

    interpreter.router.chat = unexpected_model_call
    result = await interpreter.interpret(message)

    assert result.intent == "chat"
    assert result.capability == Capability.CHAT.value


class SafeTool(BaseTool):
    name = "safe"
    description = "safe"
    permission = "SAFE"

    async def execute(self, **kwargs):
        return {"verified": True}


class ConfirmTool(SafeTool):
    name = "confirm"
    permission = "CONFIRM"


@pytest.mark.anyio
async def test_action_authority_is_the_permission_boundary():
    registry = ToolRegistry()
    registry.register(SafeTool())
    registry.register(ConfirmTool())
    authority = ActionAuthority(registry, PermissionManager())
    assert await authority.execute("safe") == {"verified": True}
    with pytest.raises(PermissionError, match="PERMISSION_REQUIRED"):
        await authority.execute("confirm")
    assert await authority.execute("confirm", confirmed=True) == {"verified": True}
