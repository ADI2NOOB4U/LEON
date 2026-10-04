from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from backend.app.tools.registry import ToolRegistry


@dataclass(frozen=True)
class CapabilitySpec:
    id: str
    category: str
    description: str
    provider: str
    model_role: str | None = None
    latency_class: str = "normal"
    privacy_class: str = "local"
    confirmation: bool = False
    external_side_effect: bool = False
    tool_name: str | None = None
    available: Callable[[], bool] | None = None
    verifier: str = "result"
    triggers: tuple[str, ...] = field(default_factory=tuple)


class CapabilityRegistry:
    def __init__(self, specs: list[CapabilitySpec] | None = None):
        self._specs = {spec.id: spec for spec in (specs or default_capabilities())}

    def get(self, capability_id: str) -> CapabilitySpec | None:
        return self._specs.get(capability_id)

    def list(self) -> list[CapabilitySpec]:
        return list(self._specs.values())

    def availability(self, spec: CapabilitySpec, tools: ToolRegistry | None = None) -> bool:
        if spec.tool_name and tools is not None and tools.get(spec.tool_name) is None:
            return False
        return spec.available() if spec.available else True


def default_capabilities() -> list[CapabilitySpec]:
    # Availability is intentionally conservative. A route can be described
    # even when its optional provider is not configured on this machine.
    return [
        CapabilitySpec("chat.general", "CHAT", "General conversation", "local", "general", "low", "local", triggers=("hello", "what are you")),
        CapabilitySpec("coding.local", "CODING", "Local coding model", "ollama", "coding", "normal", "private", True, True, triggers=("code", "build", "debug", "implement", "run tests")),
        CapabilitySpec("system.datetime", "DATETIME", "Operating system clock", "local", None, "ultra_low", "local", verifier="result", tool_name="get_datetime", triggers=("time", "date", "today", "tomorrow")),
        CapabilitySpec("system.state", "SYSTEM_STATE", "Current system status and activity", "local", None, "ultra_low", "local", verifier="result", triggers=("what are you doing", "what are you up to", "how are you")),
        CapabilitySpec("weather.current", "WEATHER", "Current weather for an explicit location", "weather", None, "normal", "public", triggers=("weather", "forecast", "temperature")),
        CapabilitySpec("system.stats", "SYSTEM_STATS", "CPU, memory and disk statistics", "local", None, "ultra_low", "local", tool_name="system_stats", triggers=("cpu", "memory usage", "disk usage")),
        CapabilitySpec("system.processes", "PROCESSES", "Running process list", "local", None, "low", "local", tool_name="list_processes", triggers=("processes", "running")),
        CapabilitySpec("desktop.applications", "APPLICATIONS", "Open desktop applications", "local", "", "low", "local", True, True, tool_name="open_app", triggers=("open", "launch", "start")),
        CapabilitySpec("files.local", "FILES", "Local filesystem tools", "local", None, "normal", "private", True, True, triggers=("file", "folder", "directory")),
        CapabilitySpec("browser.local", "BROWSER", "Local browser tools", "local", None, "normal", "public", True, True, triggers=("browser", "website", "url")),
        CapabilitySpec("research.current", "RESEARCH", "Current public information", "research", "research", "high", "public", triggers=("latest", "current", "recent", "news", "today")),
        CapabilitySpec("vision.local", "VISION", "Local image analysis", "ollama", "vision", "high", "private", triggers=("image", "picture", "screenshot")),
        CapabilitySpec("screen.local", "SCREEN_ANALYSIS", "Capture and analyze the screen", "local-vision", "vision", "high", "private", triggers=("on my screen", "screen")),
        CapabilitySpec("computer.diagnose", "SCREEN_DIAGNOSIS", "Diagnose errors and problems on the screen", "local-vision", "vision", "high", "private", triggers=("what's wrong on my screen", "why is my code failing", "diagnose screen", "fix this error")),
        CapabilitySpec("computer.observe", "COMPUTER_OBSERVE", "Observe computer and screen state", "local", None, "low", "private", triggers=("what application am i using", "active app", "screen status")),
        CapabilitySpec("computer.act", "COMPUTER_USE", "Execute safe computer actions", "local", None, "normal", "private", True, True, triggers=("click", "type", "hotkey", "focus")),
        CapabilitySpec("memory.local", "MEMORY", "Relevant local memory", "local", None, "low", "private", triggers=("remember", "what did i call", "what did i tell")),
        CapabilitySpec("tasks.autonomous", "TASKS", "Existing planner/worker task system", "local", None, "high", "private", True, True, triggers=("create a project", "multi-step", "fix failures")),
        CapabilitySpec("scheduler.local", "SCHEDULER", "Scheduled jobs and reminders", "local", None, "normal", "private", True, True, triggers=("remind", "schedule")),
        CapabilitySpec("notifications.local", "NOTIFICATIONS", "Local notification providers", "local", None, "normal", "private", True, True, triggers=("notify", "notification")),
        CapabilitySpec("media.spotify", "SPOTIFY", "Spotify and local media playback", "spotify", None, "normal", "private", True, True, verifier="playback_state", triggers=("spotify", "play", "pause", "resume", "what's playing")),
        CapabilitySpec("git.local", "GIT", "Local git tools", "local", "coding", "normal", "private", True, True, triggers=("git", "commit", "branch")),
        CapabilitySpec("email.local", "EMAIL", "Configured Gmail/email tools", "local", None, "normal", "private", True, True, tool_name="send_email", triggers=("email", "gmail", "send")),
    ]
