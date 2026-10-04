from __future__ import annotations

from backend.app.computer.actions import ComputerActionExecutor
from backend.app.computer.controller import ComputerController, computer_controller
from backend.app.computer.observation import ObservationService, observation_service
from backend.app.computer.safety import (
    ALLOWLISTED_APPLICATION_KEYS,
    is_application_allowed,
    sanitize_visual_data,
    score_action_risk,
    validate_target_safety,
)
from backend.app.computer.schemas import (
    ActionRisk,
    ComputerAction,
    ComputerActionType,
    ComputerState,
    ExecutionMetrics,
    ExecutionResult,
    Observation,
    ScreenInfo,
    TargetBounds,
    TargetLocation,
    VerificationResult,
    VisualTarget,
)
from backend.app.computer.targets import find_target_by_query, parse_targets_from_vision
from backend.app.computer.verifier import ComputerActionVerifier
from backend.app.computer.windows import (
    focus_window_by_title,
    get_active_window_info,
    list_running_applications,
)

__all__ = [
    "ALLOWLISTED_APPLICATION_KEYS",
    "ActionRisk",
    "ComputerAction",
    "ComputerActionExecutor",
    "ComputerActionType",
    "ComputerActionVerifier",
    "ComputerController",
    "ComputerState",
    "ExecutionMetrics",
    "ExecutionResult",
    "Observation",
    "ObservationService",
    "ScreenInfo",
    "TargetBounds",
    "TargetLocation",
    "VerificationResult",
    "VisualTarget",
    "computer_controller",
    "find_target_by_query",
    "focus_window_by_title",
    "get_active_window_info",
    "is_application_allowed",
    "list_running_applications",
    "observation_service",
    "parse_targets_from_vision",
    "sanitize_visual_data",
    "score_action_risk",
    "validate_target_safety",
]
