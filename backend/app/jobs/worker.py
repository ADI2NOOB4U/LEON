import asyncio
import json
import threading
import time
from datetime import datetime, timezone
from typing import Protocol

from backend.app.core.planner import planner_service
from backend.app.jobs.task_manager import (
    get_next_queued_task,
    get_task,
    log_event,
    recover_interrupted_tasks,
    set_stage,
    update_task,
)
from backend.app.notifications.service import NotificationService, notification_service
from backend.app.security.permissions import PermissionManager
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.system_tools import system_registry


class StepExecutor(Protocol):
    def execute(self, step: dict) -> str:
        """Execute one planned step and return its result."""


class TemporaryStepExecutor:
    def execute(self, step: dict) -> str:
        return f"Temporary execution completed: {step['title']}"


class LeonWorker:

    def __init__(
        self,
        executor: StepExecutor | None = None,
        registry: ToolRegistry | None = None,
        permission_manager: PermissionManager | None = None,
        notifications: NotificationService | None = None,
    ):
        self._running = False
        self._thread = None
        self._executor = executor or TemporaryStepExecutor()
        self._registry = registry or system_registry
        self._permission_manager = permission_manager or PermissionManager()
        self._notifications = notifications or notification_service

    def start(self):
        if self._running:
            return

        # A process can exit while a tool is in flight.  Requeue only the
        # interrupted work; completed steps remain durable and are skipped.
        recover_interrupted_tasks()
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="LEON-Worker",
        )
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            task = get_next_queued_task()

            if not task:
                time.sleep(1)
                continue

            self._execute(task)

    def _cancelled(self, task_id: int) -> bool:
        task = get_task(task_id)
        return bool(task and task["cancel_requested"])

    def _execute(self, task: dict):
        task_id = task["id"]
        current_step = None

        update_task(
            task_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            set_stage(task_id, "planning", 10, "Task plan initialized.")
            plan = planner_service.get_plan(task_id)

            if not plan:
                # Command-created tasks intentionally remain lightweight. The
                # durable plan is generated here so worker restarts can resume
                # from the same task record.
                plan = asyncio.run(planner_service.generate_plan(task_id))
                log_event(task_id, "planned", "Task plan generated.")

            if plan:
                if self._cancelled(task_id):
                    return self._cancel(task_id)

                set_stage(task_id, "executing", 10, "Execution started.")
                total_steps = len(plan["steps"])
                completed_steps = sum(
                    step["status"] == "completed" for step in plan["steps"]
                )
                if total_steps:
                    update_task(
                        task_id,
                        progress=min(90, int(90 * completed_steps / total_steps)),
                    )

                for step in planner_service.get_pending_steps(task_id):
                    if self._cancelled(task_id):
                        return self._cancel(task_id)

                    current_step = step
                    self._transition_step(step, "running")
                    try:
                        result = self._execute_step(step)
                    except Exception as exc:
                        self._transition_step(step, "failed", str(exc))
                        raise

                    self._transition_step(step, "completed", result)
                    current_step = None
                    completed_steps += 1
                    update_task(
                        task_id,
                        status="executing",
                        current_stage="executing",
                        progress=min(90, int(90 * completed_steps / total_steps)),
                    )
            set_stage(
                task_id,
                "verifying",
                90,
                "Verifying task result.",
            )
            if self._cancelled(task_id):
                return self._cancel(task_id)

            self._verify_plan(task_id)
            final_result = self._result_summary(task_id, task["title"])

            update_task(
                task_id,
                status="completed",
                current_stage="completed",
                progress=100,
                result=final_result,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

            log_event(
                task_id,
                "completed",
                "Task completed successfully.",
            )
            self._notifications.notify_task_outcome(get_task(task_id), "completed")

        except Exception as exc:
            current = get_task(task_id)

            if current and current["retry_count"] < current["max_retries"]:
                retry_count = current["retry_count"] + 1

                update_task(
                    task_id,
                    status="queued",
                    current_stage="queued",
                    progress=0,
                    retry_count=retry_count,
                    error=str(exc),
                )

                if current_step is not None:
                    self._transition_step(current_step, "pending")

                log_event(
                    task_id,
                    "retry",
                    f"Retrying task ({retry_count}/{current['max_retries']}).",
                )
            else:
                update_task(
                    task_id,
                    status="failed",
                    current_stage="failed",
                    error=str(exc),
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

                log_event(
                    task_id,
                    "failed",
                    str(exc),
                )
                self._notifications.notify_task_outcome(get_task(task_id), "failed")

    @staticmethod
    def _transition_step(
        step: dict, status: str, result: str | None = None
    ) -> None:
        updated = planner_service.update_step(step["id"], status, result)
        if updated is None:
            raise ValueError(f"Plan step {step['id']} no longer exists")
        log_event(
            step["task_id"],
            f"step_{status}",
            f"Step {step['step_number']} '{step['title']}' transitioned to {status}.",
        )

    def _execute_step(self, step: dict) -> str:
        """Run a registered tool, or retain the legacy executor for ordinary steps."""
        tool_name = step.get("tool_name")
        if not tool_name:
            return self._executor.execute(step)

        tool = self._registry.get(tool_name)
        if tool is None:
            raise ValueError(f"Unknown tool: {tool_name}")
        if not self._permission_manager.can_execute(tool, confirmed=False):
            raise PermissionError(f"Tool '{tool_name}' cannot be executed")

        arguments = step.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be an object")

        log_event(step["task_id"], "tool_execution", f"Executing tool '{tool_name}'.")
        result = asyncio.run(self._registry.execute(tool_name, **arguments))
        if tool_name == "coding_execute":
            exit_code = result.get("exit_code") if isinstance(result, dict) else None
            timed_out = result.get("timed_out") if isinstance(result, dict) else False
            log_event(
                step["task_id"],
                "coding_execution",
                f"Coding command completed with exit code {exit_code}; timed_out={timed_out}.",
            )
            if timed_out or exit_code != 0:
                raise RuntimeError(
                    f"Coding command failed (exit code {exit_code}; timed_out={timed_out})."
                )
        return json.dumps(result, default=str)

    @staticmethod
    def _result_summary(task_id: int, title: str) -> str:
        """Return a concise deterministic result assembled from verified steps."""
        plan = planner_service.get_plan(task_id)
        completed = [step for step in (plan or {}).get("steps", []) if step["status"] == "completed"]
        if not completed:
            return f"Task '{title}' completed successfully."
        results = [step["result"] for step in completed if step["result"] is not None]
        suffix = f" ({len(completed)} step{'s' if len(completed) != 1 else ''})"
        if not results:
            return f"Task '{title}' completed successfully{suffix}."
        return f"Task '{title}' completed successfully{suffix}: {'; '.join(results)}"

    @staticmethod
    def _verify_plan(task_id: int) -> None:
        plan = planner_service.get_plan(task_id)
        if plan and any(step["status"] != "completed" for step in plan["steps"]):
            raise RuntimeError("Task verification failed: not all plan steps completed")

    def _cancel(self, task_id: int):
        update_task(
            task_id,
            status="cancelled",
            current_stage="cancelled",
            progress=0,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        log_event(
            task_id,
            "cancelled",
            "Task cancelled before completion.",
        )


worker = LeonWorker()
