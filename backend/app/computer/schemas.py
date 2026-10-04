from __future__ import annotations

from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field


class ActionRisk(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"


class ComputerState(StrEnum):
    IDLE = "IDLE"
    OBSERVING = "OBSERVING"
    PLANNING = "PLANNING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    ACTING = "ACTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ComputerActionType(StrEnum):
    OBSERVE = "observe"
    FOCUS_APP = "focus_app"
    LAUNCH_APP = "launch_app"
    CLICK_TARGET = "click_target"
    TYPE_TEXT = "type_text"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    SELECT_MENU = "select_menu"
    BROWSER_NAV = "browser_nav"
    INSPECT_WORKSPACE = "inspect_workspace"
    DIAGNOSE_ERROR = "diagnose_error"


class TargetLocation(BaseModel):
    x: int = Field(ge=0, description="X coordinate in pixels")
    y: int = Field(ge=0, description="Y coordinate in pixels")


class TargetBounds(BaseModel):
    left: int = Field(ge=0)
    top: int = Field(ge=0)
    width: int = Field(ge=0)
    height: int = Field(ge=0)


class VisualTarget(BaseModel):
    id: str
    label: str
    type: str = "element"  # button, input, menu, link, error, text, dialog, terminal, window
    location: TargetLocation
    bounds: TargetBounds | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.9)
    freshness_timestamp: str
    app_context: str | None = None
    raw_text: str | None = None


class ScreenInfo(BaseModel):
    width: int = 1920
    height: int = 1080
    scale_factor: float = 1.0
    is_captured: bool = True


class Observation(BaseModel):
    id: str
    timestamp: str
    screen: ScreenInfo
    active_application: str | None = None
    active_window: str | None = None
    visible_text: str | None = None
    screenshot_available: bool = True
    running_applications: list[str] = Field(default_factory=list)
    detected_targets: list[VisualTarget] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    error_summary: str | None = None


class ComputerAction(BaseModel):
    action_type: ComputerActionType
    app_name: str | None = None
    target_id: str | None = None
    target_label: str | None = None
    coordinates: TargetLocation | None = None
    text: str | None = None
    hotkeys: list[str] | None = None
    scroll_direction: str | None = None  # "up", "down"
    url: str | None = None
    path: str | None = None
    observation_id: str | None = None
    confirmed: bool = False
    risk: ActionRisk = ActionRisk.LOW


class VerificationResult(BaseModel):
    verified: bool
    code: str = "OK"
    reason: str
    state_changes: dict[str, Any] = Field(default_factory=dict)


class ExecutionMetrics(BaseModel):
    observation_ms: float = 0.0
    vision_ms: float = 0.0
    action_ms: float = 0.0
    verification_ms: float = 0.0
    total_ms: float = 0.0


class ExecutionResult(BaseModel):
    success: bool
    state: ComputerState
    action: ComputerAction | None = None
    observation_before: Observation | None = None
    observation_after: Observation | None = None
    verification: VerificationResult | None = None
    message: str
    error: str | None = None
    metrics: ExecutionMetrics = Field(default_factory=ExecutionMetrics)
