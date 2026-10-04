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
    SYSTEM_STATE = "SYSTEM_STATE"
    WEATHER = "WEATHER"
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
    EMAIL = "EMAIL"


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
        or re.search(r"\b(?:what\s+time\s+is\s+it|what\s+is\s+today(?:'s|s)?\s+date|what\s+is\s+today(?:'s|s)?\s+date\s+and\s+time)\b", value)
        or "date and time" in value
        or "time and date" in value
    )


def is_system_state_request(text: str) -> bool:
    """Detect direct status questions such as "what are you doing?"."""
    value = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    if not value:
        return False

    return bool(
        re.search(r"\bwhat\s+(?:are|is)\s+(?:you|leon)\s+(?:doing|up to|working on|busy with|doing right now)\b", value)
        or re.search(r"\b(?:what\s+are\s+you\s+doing\?|what\s+are\s+you\s+up\s+to\?)", value)
        or re.search(r"\b(?:how\s+are\s+you\s+doing|how\s+are\s+you)\b", value)
    )


def is_weather_request(text: str) -> bool:
    return bool(re.search(r"\b(?:weather|forecast|temperature)\b", text, re.I))


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
    if is_system_state_request(value):
        return CapabilityIntent(Capability.SYSTEM_STATE, "status", title=text)
    if is_weather_request(value):
        return CapabilityIntent(Capability.WEATHER, "current", title=text)
    if re.search(r"\b(?:send|write|compose)\b.*\b(?:email|e-mail|gmail)\b|\b(?:email|e-mail|gmail)\b.*\b(?:send|write|compose)\b", value):
        return CapabilityIntent(Capability.EMAIL, "send", title=text, requires_confirmation=True)
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
    hindi_media = re.search(r"\b(?:spotify\s+chalao|gaana\s+(?:pause|resume)\s+karo|agla\s+gaana\s+chalao|pichla\s+gaana\s+chalao|abhi\s+kaunsa\s+gaana\s+baj\s+raha\s+hai)\b", value)
    if hindi_media:
        if "kaunsa" in value or "baj raha" in value:
            return CapabilityIntent(Capability.MEDIA, "current", title=text)
        if "pause" in value:
            return CapabilityIntent(Capability.MEDIA, "pause", title=text)
        if "resume" in value:
            return CapabilityIntent(Capability.MEDIA, "resume", title=text)
        if "agla" in value:
            return CapabilityIntent(Capability.MEDIA, "next", title=text)
        if "pichla" in value:
            return CapabilityIntent(Capability.MEDIA, "previous", title=text)
        return CapabilityIntent(Capability.MEDIA, "play", title=text)
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
