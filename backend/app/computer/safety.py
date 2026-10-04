from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Tuple

from backend.app.computer.schemas import (
    ActionRisk,
    ComputerAction,
    ComputerActionType,
    Observation,
    VisualTarget,
)
from backend.app.tools.applications import APPLICATIONS, resolve_application
from backend.app.security.web_security import redact_secrets

ALLOWLISTED_APPLICATION_KEYS = {app.key for app in APPLICATIONS} | {
    "vscode", "chrome", "edge", "spotify", "vlc", "discord", "steam", "notepad", "explorer"
}

_SENSITIVE_PATTERNS = [
    re.compile(r"\b(?:password|passwd|secret|api[_-]?key|token|auth|bearer|private[_-]?key)\b", re.IGNORECASE),
    re.compile(r"\b(?:format\s+[a-z]:|rmdir\s+/s|del\s+/f|rm\s+-rf|drop\s+database)\b", re.IGNORECASE),
]

_INJECTION_DIRECTIVES = [
    re.compile(r"\b(?:ignore\s+(?:all\s+)?previous\s+instructions|system\s+prompt|new\s+system\s+instruction|you\s+must\s+now|override\s+all\s+rules)\b", re.IGNORECASE),
    re.compile(r"\b(?:exfiltrate|send\s+tokens|reveal\s+passwords?|disable\s+security|bypass\s+permissions?)\b", re.IGNORECASE),
]

TARGET_MAX_AGE_SECONDS = 60.0
MIN_TARGET_CONFIDENCE = 0.40


def is_application_allowed(app_name: str | None) -> bool:
    if not app_name or not app_name.strip():
        return False
    app = resolve_application(app_name.strip())
    if app and app.key in ALLOWLISTED_APPLICATION_KEYS:
        return True
    normalized = app_name.strip().lower().removesuffix(".exe").replace(" ", "")
    return normalized in ALLOWLISTED_APPLICATION_KEYS


def score_action_risk(action: ComputerAction) -> ActionRisk:
    """Determine the authoritative risk score of a requested computer action."""
    action_type = action.action_type

    if action_type in {ComputerActionType.OBSERVE, ComputerActionType.INSPECT_WORKSPACE}:
        return ActionRisk.LOW

    if action_type == ComputerActionType.FOCUS_APP:
        if action.app_name and not is_application_allowed(action.app_name):
            return ActionRisk.BLOCKED
        return ActionRisk.LOW

    if action_type == ComputerActionType.LAUNCH_APP:
        if not action.app_name or not is_application_allowed(action.app_name):
            return ActionRisk.BLOCKED
        return ActionRisk.MEDIUM

    if action_type == ComputerActionType.CLICK_TARGET:
        label = (action.target_label or "").lower()
        if any(pat.search(label) for pat in _SENSITIVE_PATTERNS):
            return ActionRisk.HIGH
        return ActionRisk.LOW if action.risk == ActionRisk.LOW else ActionRisk.MEDIUM

    if action_type == ComputerActionType.TYPE_TEXT:
        text = action.text or ""
        if any(pat.search(text) for pat in _SENSITIVE_PATTERNS):
            return ActionRisk.HIGH
        return ActionRisk.MEDIUM

    if action_type == ComputerActionType.HOTKEY:
        keys = [k.lower() for k in (action.hotkeys or [])]
        # Potentially destructive combinations
        if "delete" in keys or "alt+f4" in keys or "ctrl+shift+w" in keys:
            return ActionRisk.HIGH
        return ActionRisk.LOW

    if action_type == ComputerActionType.BROWSER_NAV:
        url = action.url or ""
        if not url.startswith(("http://", "https://")):
            return ActionRisk.BLOCKED
        return ActionRisk.LOW

    if action_type == ComputerActionType.DIAGNOSE_ERROR:
        return ActionRisk.LOW

    return ActionRisk.MEDIUM


def validate_target_safety(target: VisualTarget, observation: Observation) -> Tuple[bool, str]:
    """Validate that a target is fresh, within bounds, and safe to interact with."""
    # Check bounds
    width = observation.screen.width
    height = observation.screen.height
    loc = target.location

    if loc.x < 0 or loc.x > width or loc.y < 0 or loc.y > height:
        return False, f"Target coordinate ({loc.x}, {loc.y}) is outside screen bounds ({width}x{height})"

    # Check confidence
    if target.confidence < MIN_TARGET_CONFIDENCE:
        return False, f"Target confidence {target.confidence:.2f} is below minimum threshold {MIN_TARGET_CONFIDENCE:.2f}"

    # Check freshness
    try:
        freshness_dt = datetime.fromisoformat(target.freshness_timestamp)
        now_dt = datetime.now(timezone.utc)
        if freshness_dt.tzinfo is None:
            freshness_dt = freshness_dt.replace(tzinfo=timezone.utc)
        age_seconds = (now_dt - freshness_dt).total_seconds()
        if age_seconds > TARGET_MAX_AGE_SECONDS:
            return False, f"Target is stale ({age_seconds:.1f}s old, max allowed {TARGET_MAX_AGE_SECONDS}s)"
    except (ValueError, TypeError):
        pass  # If timestamp format is unparseable, proceed cautiously

    # Check for prompt injection in target label
    if any(pat.search(target.label) for pat in _INJECTION_DIRECTIVES):
        return False, "Target contains suspicious instruction directive and was blocked"

    return True, "Target is valid and safe"


def sanitize_visual_data(raw_text: str | None) -> str:
    """Ensure visual/OCR text is sanitized and tagged as untrusted observation data."""
    if not raw_text:
        return ""
    sanitized, _ = redact_secrets(raw_text)
    return sanitized
