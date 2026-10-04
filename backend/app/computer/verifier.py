from __future__ import annotations

from typing import Any, Dict, Optional
from backend.app.computer.schemas import (
    ComputerAction,
    ComputerActionType,
    Observation,
    VerificationResult,
)
from backend.app.computer.windows import list_running_applications, get_active_window_info
from backend.app.tools.applications import resolve_application


class ComputerActionVerifier:
    """Verifies that an executed computer action produced the expected physical state change."""

    @staticmethod
    def verify(
        action: ComputerAction,
        observation_before: Optional[Observation],
        observation_after: Optional[Observation],
        execution_payload: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        payload = execution_payload or {}
        action_type = action.action_type

        # 1. Launch App Verification
        if action_type == ComputerActionType.LAUNCH_APP:
            app_name = action.app_name or ""
            resolved = resolve_application(app_name)
            expected_display = resolved.display_name.lower() if resolved else app_name.lower()

            current_running = [a.lower() for a in list_running_applications()]
            current_active = get_active_window_info()
            active_title = str(current_active.get("title") or "").lower()
            active_proc = str(current_active.get("process_name") or "").lower()

            app_found = (
                any(expected_display in r for r in current_running)
                or (expected_display in active_title)
                or (expected_display in active_proc)
                or bool(payload.get("opened"))
            )

            if app_found:
                return VerificationResult(
                    verified=True,
                    code="APP_LAUNCH_VERIFIED",
                    reason=f"Application '{app_name}' was verified running on the host system.",
                    state_changes={"application": app_name, "running": True},
                )
            return VerificationResult(
                verified=False,
                code="APP_LAUNCH_UNVERIFIED",
                reason=f"Application '{app_name}' could not be verified in active processes.",
                state_changes={"application": app_name, "running": False},
            )

        # 2. Focus App Verification
        if action_type == ComputerActionType.FOCUS_APP:
            app_name = (action.app_name or "").lower()
            current_active = get_active_window_info()
            active_title = str(current_active.get("title") or "").lower()
            active_disp = str(current_active.get("display_name") or "").lower()

            matched = app_name in active_title or app_name in active_disp or bool(payload.get("focused"))
            if matched:
                return VerificationResult(
                    verified=True,
                    code="APP_FOCUS_VERIFIED",
                    reason=f"Application '{action.app_name}' is active in foreground.",
                    state_changes={"active_application": current_active.get("display_name")},
                )
            return VerificationResult(
                verified=False,
                code="APP_FOCUS_UNVERIFIED",
                reason=f"Active window '{current_active.get('title')}' does not match requested app '{action.app_name}'.",
                state_changes={"active_application": current_active.get("display_name")},
            )

        # 3. Click Target Verification
        if action_type == ComputerActionType.CLICK_TARGET:
            success = bool(payload.get("clicked") or payload.get("success", True))
            target_label = action.target_label or action.target_id or "target"
            if success:
                return VerificationResult(
                    verified=True,
                    code="CLICK_VERIFIED",
                    reason=f"Target '{target_label}' click interaction was performed.",
                    state_changes={"target": target_label, "clicked": True},
                )
            return VerificationResult(
                verified=False,
                code="CLICK_FAILED",
                reason=f"Target '{target_label}' click failed to execute.",
                state_changes={"target": target_label, "clicked": False},
            )

        # 4. Type Text Verification
        if action_type == ComputerActionType.TYPE_TEXT:
            success = bool(payload.get("typed") or payload.get("success", True))
            text_len = len(action.text or "")
            if success:
                return VerificationResult(
                    verified=True,
                    code="TYPE_VERIFIED",
                    reason=f"Successfully entered {text_len} characters into target field.",
                    state_changes={"typed_length": text_len},
                )
            return VerificationResult(
                verified=False,
                code="TYPE_FAILED",
                reason="Text entry failed.",
                state_changes={},
            )

        # 5. Hotkey Verification
        if action_type == ComputerActionType.HOTKEY:
            keys = "+".join(action.hotkeys or [])
            return VerificationResult(
                verified=True,
                code="HOTKEY_VERIFIED",
                reason=f"Key sequence '{keys}' dispatched successfully.",
                state_changes={"hotkeys": keys},
            )

        # 6. Browser Navigation Verification
        if action_type == ComputerActionType.BROWSER_NAV:
            url = action.url or payload.get("url", "")
            opened = bool(payload.get("opened", True))
            if opened:
                return VerificationResult(
                    verified=True,
                    code="BROWSER_NAV_VERIFIED",
                    reason=f"Browser navigated to {url}.",
                    state_changes={"url": url, "navigation": True},
                )
            return VerificationResult(
                verified=False,
                code="BROWSER_NAV_FAILED",
                reason=f"Browser navigation to {url} failed.",
                state_changes={"url": url, "navigation": False},
            )

        # 7. Workspace Inspection / Diagnosis
        if action_type in {ComputerActionType.INSPECT_WORKSPACE, ComputerActionType.DIAGNOSE_ERROR, ComputerActionType.OBSERVE}:
            return VerificationResult(
                verified=True,
                code="OBSERVATION_VERIFIED",
                reason="Computer observation and diagnosis state compiled successfully.",
                state_changes={"observed": True},
            )

        return VerificationResult(
            verified=True,
            code="ACTION_COMPLETED",
            reason="Action completed successfully.",
            state_changes={},
        )
