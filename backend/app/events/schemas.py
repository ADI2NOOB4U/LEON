from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Dict, Optional
import uuid


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventTopic(StrEnum):
    MISSION_CREATED = "mission.created"
    MISSION_STARTED = "mission.started"
    MISSION_STEP_STARTED = "mission.step_started"
    MISSION_STEP_COMPLETED = "mission.step_completed"
    MISSION_REPAIR_STARTED = "mission.repair_started"
    MISSION_RETRY = "mission.retry"
    MISSION_WAITING = "mission.waiting"
    MISSION_CONFIRMATION_REQUIRED = "mission.confirmation_required"
    MISSION_VERIFICATION_PASSED = "mission.verification_passed"
    MISSION_COMPLETED = "mission.completed"
    MISSION_FAILED = "mission.failed"
    MISSION_CANCELLED = "mission.cancelled"

    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    TASK_PAUSED = "task.paused"
    TASK_RESUMED = "task.resumed"
    
    VOICE_STARTED = "voice.started"
    VOICE_TRANSCRIPT = "voice.transcript"
    VOICE_COMPLETED = "voice.completed"
    VOICE_INTERRUPTED = "voice.interrupted"
    
    VISION_COMPLETED = "vision.completed"
    COMPUTER_ACTION = "computer.action"
    
    MEDIA_CHANGED = "media.changed"
    BROWSER_NAVIGATED = "browser.navigated"
    
    SECURITY_ALERT = "security.alert"
    CONFIRMATION_REQUIRED = "security.confirmation_required"
    HEALTH_CHANGED = "system.health_changed"
    PROVIDER_STATUS = "system.provider_status"
    VOICE_COMMAND_DETECTED = "voice.command_detected"
    SECURITY_VIOLATION = "security.violation"

    MEMORY_CREATED = "memory.created"
    MEMORY_UPDATED = "memory.updated"
    MEMORY_CORRECTED = "memory.corrected"
    MEMORY_DELETED = "memory.deleted"
    MEMORY_CONFIRMED = "memory.confirmed"


@dataclass(frozen=True)
class Event:
    topic: str
    payload: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:10]}")
    timestamp: str = field(default_factory=now_iso)
    source: str = "core"


# Compatibility name used by the V2 event tests and integrations.
LeonEvent = Event
