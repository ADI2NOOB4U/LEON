from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional

from backend.app.computer.actions import ComputerActionExecutor
from backend.app.computer.observation import ObservationService, observation_service
from backend.app.computer.safety import (
    is_application_allowed,
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
    VerificationResult,
)
from backend.app.computer.targets import find_target_by_query
from backend.app.computer.verifier import ComputerActionVerifier
from backend.app.core.action_authority import ActionAuthority
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.system_tools import system_registry


class ComputerController:
    """The central orchestrator for Computer Use and Screen Intelligence."""

    def __init__(
        self,
        observations: Optional[ObservationService] = None,
        executor: Optional[ComputerActionExecutor] = None,
        verifier: Optional[ComputerActionVerifier] = None,
        registry: Optional[ToolRegistry] = None,
        authority: Optional[ActionAuthority] = None,
    ):
        self.observations = observations or observation_service
        self.registry = registry or system_registry
        self.authority = authority or ActionAuthority(self.registry)
        self.executor = executor or ComputerActionExecutor(self.registry, self.authority)
        self.verifier = verifier or ComputerActionVerifier()
        self._state = ComputerState.IDLE
        self._cancel_requested = False
        self._lock = asyncio.Lock()

    @property
    def state(self) -> ComputerState:
        return self._state

    def cancel(self) -> None:
        """Interrupt and cancel any running computer execution loop."""
        self._cancel_requested = True
        self._state = ComputerState.CANCELLED

    async def observe_current_state(
        self,
        include_vision: bool = True,
        prompt: str | None = None,
        mode: str = "screen",
    ) -> Observation:
        """Capture and return the current computer screen and OS state."""
        self._state = ComputerState.OBSERVING
        try:
            obs = await self.observations.observe(include_vision=include_vision, prompt=prompt, mode=mode)
            self._state = ComputerState.IDLE
            return obs
        except Exception:
            self._state = ComputerState.FAILED
            raise

    async def diagnose_screen(
        self,
        question: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Diagnose visible errors and current state on the user's screen."""
        started = time.perf_counter()
        self._cancel_requested = False
        self._state = ComputerState.OBSERVING

        obs_started = time.perf_counter()
        obs = await self.observations.observe(
            include_vision=True,
            prompt=question or "Identify what is on the screen, active errors, traceback messages, or failing states.",
            mode="screen",
        )
        obs_ms = (time.perf_counter() - obs_started) * 1000

        self._state = ComputerState.PLANNING

        # Correlate screen info with running applications and active window
        diagnosis = {
            "observation_id": obs.id,
            "timestamp": obs.timestamp,
            "active_application": obs.active_application,
            "active_window": obs.active_window,
            "screenshot_available": obs.screenshot_available,
            "visible_summary": obs.visible_text,
            "error_detected": bool(obs.error_summary),
            "error_summary": obs.error_summary,
            "targets_count": len(obs.detected_targets),
            "diagnostics": obs.diagnostics,
            "latency_ms": (time.perf_counter() - started) * 1000,
        }

        self._state = ComputerState.COMPLETED
        return diagnosis

    async def execute_loop(
        self,
        action: ComputerAction,
        *,
        confirmed: bool = False,
        timeout_seconds: float = 30.0,
    ) -> ExecutionResult:
        """Execute a full OBSERVE -> AUTHORIZE -> ACT -> OBSERVE AGAIN -> VERIFY loop."""
        async with self._lock:
            self._cancel_requested = False
            total_started = time.perf_counter()
            metrics = ExecutionMetrics()

            try:
                # 1. OBSERVE (Initial state)
                self._state = ComputerState.OBSERVING
                obs_start = time.perf_counter()
                obs_before = await self.observations.observe(include_vision=False)
                metrics.observation_ms = (time.perf_counter() - obs_start) * 1000

                if self._cancel_requested:
                    self._state = ComputerState.CANCELLED
                    return ExecutionResult(
                        success=False,
                        state=ComputerState.CANCELLED,
                        action=action,
                        observation_before=obs_before,
                        message="Computer action cancelled by user before execution.",
                        metrics=metrics,
                    )

                # 2. TARGET VALIDATION (if target interaction)
                if action.action_type == ComputerActionType.CLICK_TARGET and action.target_id:
                    target = next((t for t in obs_before.detected_targets if t.id == action.target_id), None)
                    if target:
                        is_safe, reason = validate_target_safety(target, obs_before)
                        if not is_safe:
                            self._state = ComputerState.FAILED
                            return ExecutionResult(
                                success=False,
                                state=ComputerState.FAILED,
                                action=action,
                                observation_before=obs_before,
                                message=f"Target safety validation failed: {reason}",
                                error=reason,
                                metrics=metrics,
                            )

                # 3. AUTHORIZATION & RISK CHECK
                self._state = ComputerState.PLANNING
                risk = score_action_risk(action)
                action.risk = risk

                if risk == ActionRisk.BLOCKED:
                    self._state = ComputerState.FAILED
                    return ExecutionResult(
                        success=False,
                        state=ComputerState.FAILED,
                        action=action,
                        observation_before=obs_before,
                        message=f"Action '{action.action_type}' is BLOCKED by safety policy.",
                        error="ACTION_BLOCKED",
                        metrics=metrics,
                    )

                if risk == ActionRisk.HIGH and not confirmed:
                    self._state = ComputerState.AWAITING_CONFIRMATION
                    return ExecutionResult(
                        success=False,
                        state=ComputerState.AWAITING_CONFIRMATION,
                        action=action,
                        observation_before=obs_before,
                        message=f"Action '{action.action_type}' requires explicit user confirmation.",
                        metrics=metrics,
                    )

                # 4. ACT
                self._state = ComputerState.ACTING
                act_start = time.perf_counter()
                execution_payload = await asyncio.wait_for(
                    self.executor.execute_action(action, confirmed=confirmed),
                    timeout=timeout_seconds,
                )
                metrics.action_ms = (time.perf_counter() - act_start) * 1000

                if self._cancel_requested:
                    self._state = ComputerState.CANCELLED
                    return ExecutionResult(
                        success=False,
                        state=ComputerState.CANCELLED,
                        action=action,
                        observation_before=obs_before,
                        message="Computer action cancelled after execution.",
                        metrics=metrics,
                    )

                # 5. OBSERVE AGAIN (Post-action state)
                self._state = ComputerState.VERIFYING
                obs_post_start = time.perf_counter()
                obs_after = await self.observations.observe(include_vision=False)
                metrics.observation_ms += (time.perf_counter() - obs_post_start) * 1000

                # 6. VERIFY
                ver_start = time.perf_counter()
                verification = self.verifier.verify(
                    action=action,
                    observation_before=obs_before,
                    observation_after=obs_after,
                    execution_payload=execution_payload,
                )
                metrics.verification_ms = (time.perf_counter() - ver_start) * 1000
                metrics.total_ms = (time.perf_counter() - total_started) * 1000

                success = verification.verified
                self._state = ComputerState.COMPLETED if success else ComputerState.FAILED

                return ExecutionResult(
                    success=success,
                    state=self._state,
                    action=action,
                    observation_before=obs_before,
                    observation_after=obs_after,
                    verification=verification,
                    message=verification.reason,
                    metrics=metrics,
                )

            except asyncio.TimeoutError:
                self._state = ComputerState.FAILED
                metrics.total_ms = (time.perf_counter() - total_started) * 1000
                return ExecutionResult(
                    success=False,
                    state=ComputerState.FAILED,
                    action=action,
                    message=f"Computer action timed out after {timeout_seconds}s.",
                    error="TIMEOUT",
                    metrics=metrics,
                )
            except PermissionError as exc:
                self._state = ComputerState.FAILED
                metrics.total_ms = (time.perf_counter() - total_started) * 1000
                return ExecutionResult(
                    success=False,
                    state=ComputerState.FAILED,
                    action=action,
                    message=str(exc),
                    error="PERMISSION_DENIED",
                    metrics=metrics,
                )
            except Exception as exc:
                self._state = ComputerState.FAILED
                metrics.total_ms = (time.perf_counter() - total_started) * 1000
                return ExecutionResult(
                    success=False,
                    state=ComputerState.FAILED,
                    action=action,
                    message=f"Computer action failed: {exc}",
                    error=str(exc),
                    metrics=metrics,
                )


computer_controller = ComputerController()
