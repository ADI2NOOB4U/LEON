"""Deterministic capability routing for natural-language desktop commands.

This module only proposes a capability. It never executes an OS action. The
registry/permission boundary remains the authority for execution.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum


class Capability(StrEnum):
    CHAT = "CHAT"
    DATETIME = "DATETIME"
    VISION = "VISION"
    OCR = "OCR"
    SCREEN = "SCREEN"
    BROWSER = "BROWSER"
    RESEARCH = "RESEARCH"
    MEDIA = "MEDIA"
    SYSTEM = "SYSTEM"
    FILES = "FILES"
    TASKS = "TASKS"
    CODING = "CODING"
    SCHEDULER = "SCHEDULER"
    NOTIFICATIONS = "NOTIFICATIONS"


@dataclass(frozen=True)
class CapabilityIntent:
    capability: Capability
    action: str = "chat"
    title: str = ""
    arguments: dict[str, str] = field(default_factory=dict)
    requires_confirmation: bool = False


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_datetime_request(text: str) -> bool:
    """Detect a direct request for the local clock, not live-world research."""
    value = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    if not value:
        return False
    return bool(
        re.search(
            r"^(?:leon )?(?:please )?(?:what(?:s| is)?(?: the)?|tell me(?: the)?|give me(?: the)?)\s+"
            r"(?:current )?(?:date and time|time and date|date|time)\b",
            value,
        )
        or re.search(r"\b(?:current|today s|todays)\s+(?:date and time|time and date|date|time)\b", value)
        or re.search(r"\b(?:date and time|time and date|date|time)\b(?:\s+\w+){0,3}\s+\b(?:is it|now|currently)\b", value)
        or "date and time" in value
        or "time and date" in value
    )


def classify_command(text: str) -> CapabilityIntent:
    """Classify obvious commands without invoking a model.

    Ambiguous or complex requests intentionally fall back to TASKS/CHAT rather
    than guessing a side-effectful action.
    """
    value = _normalized(text)
    if not value:
        return CapabilityIntent(Capability.CHAT)

    if is_datetime_request(value):
        return CapabilityIntent(Capability.DATETIME, "current")
    if re.search(r"\b(cancel|stop)\b.*\b(task|that|what you(?:'re| are) doing)\b|^stop$|^cancel that$", value):
        return CapabilityIntent(Capability.TASKS, "cancel")
    if re.search(r"\b(recent|current) tasks?\b|task status", value):
        return CapabilityIntent(Capability.TASKS, "list")
    if re.search(r"\b(remind|reminder|schedule|tomorrow at)\b", value):
        return CapabilityIntent(Capability.SCHEDULER, "create", title=text)
    if re.search(r"\b(read|what(?:'s| is) happening|what error|which application|what button|explain)\b.*\b(screen|this|error|text)\b|\b(read my screen|read what's on my screen)\b", value):
        action = "ocr" if re.search(r"\b(read|text)\b", value) else "analyze"
        return CapabilityIntent(Capability.OCR if action == "ocr" else Capability.SCREEN, action)
    if re.search(r"\b(screenshot|screen capture|capture my screen)\b", value):
        return CapabilityIntent(Capability.SCREEN, "capture")
    if re.search(r"\b(play|start|put on|listen to|pause|resume|stop|next|previous|skip|volume|what(?:'s| is) playing)\b", value):
        if "playing" in value:
            action = "current"
        elif "volume" in value:
            action = "volume"
        else:
            action = next((x for x in ("pause", "resume", "stop", "next", "previous", "skip", "play", "start") if re.search(rf"\b{x}\b", value)), "play")
        if action in {"start", "skip"}:
            action = "play" if action == "start" else "next"
        return CapabilityIntent(Capability.MEDIA, action, title=text)
    if re.search(r"\b(latest|recent|news|research|look up|search online|find more)\b", value):
        return CapabilityIntent(Capability.RESEARCH, "research", title=text)
    if re.search(r"\b(create|edit|modify|write)\b.*\b(file|folder|directory)\b", value):
        return CapabilityIntent(Capability.FILES, "write", title=text, requires_confirmation=True)
    if re.search(r"\b(open|launch|start|close)\b\s+(vscode|vs code|chrome|edge|spotify|vlc|discord|steam|notepad|file explorer)\b", value):
        action = "close" if re.search(r"\bclose\b", value) else "open"
        return CapabilityIntent(Capability.SYSTEM, action, title=text, requires_confirmation=action == "close")
    if re.search(r"\b(build|fix|debug|implement|refactor|code|run tests?)\b", value):
        return CapabilityIntent(Capability.CODING, "execute", title=text, requires_confirmation=True)
    if re.search(r"\b(open|launch|browse|navigate)\b\s+https?://|\b(open this link|search the web)\b", value):
        return CapabilityIntent(Capability.BROWSER, "navigate", title=text, requires_confirmation=True)
    return CapabilityIntent(Capability.CHAT, "chat")
