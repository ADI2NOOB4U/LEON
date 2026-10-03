import asyncio
import json
import threading
import time
from datetime import datetime, timezone
from typing import Protocol

from backend.app.core.planner import planner_service
from backend.app.core.coding_agent import CodingAgent
from backend.app.core.research_agent import ResearchAgent
from backend.app.jobs.task_manager import (
    get_next_queued_task,
    claim_task,
    get_task,
    log_event,
    recover_interrupted_tasks,
    set_stage,
    update_task,
    register_artifact,
)
from backend.app.notifications.service import NotificationService, notification_service
from backend.app.security.permissions import PermissionManager
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.system_tools import system_registry


MAX_CODING_FIX_ATTEMPTS = 3


class StepExecutor(Protocol):
    def execute(self, step: dict) -> str:
        """Execute one planned step and return its result."""


class UnconfiguredStepExecutor:
    def execute(self, step: dict) -> str:
        raise StepExecutorUnavailableError(
            f"No executor is configured for plan step '{step['title']}'."
        )


class StepExecutorUnavailableError(RuntimeError):
    """A planned step has no implementation and must not be reported as done."""


class LeonWorker:

    def __init__(
        self,
        executor: StepExecutor | None = None,
        registry: ToolRegistry | None = None,
        permission_manager: PermissionManager | None = None,
        notifications: NotificationService | None = None,
        coding_agent: CodingAgent | None = None,
    ):
        self._running = False
        self._thread = None
        self._executor = executor or UnconfiguredStepExecutor()
        self._registry = registry or system_registry
        self._permission_manager = permission_manager or PermissionManager()
        self._notifications = notifications or notification_service
        self._coding_agent = coding_agent or CodingAgent()
        self._research_agent = ResearchAgent(self._registry, self._permission_manager)

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

            if claim_task(task["id"]):
                claimed_task = get_task(task["id"])
                if claimed_task:
                    self._execute(claimed_task)

    def _cancelled(self, task_id: int) -> bool:
        task = get_task(task_id)
        return bool(task and task["cancel_requested"])

    def _execute(self, task: dict):
        if task is None:
            return

        task_id = task["id"]
        current_step = None

        update_task(
            task_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            if task.get("task_type") == "research":
                set_stage(task_id, "researching", 10, "Bounded web research started.")
                research = asyncio.run(self._research_agent.run(
                    task_id, task["title"], task.get("research_source_count", 5),
                    cancelled=lambda: self._cancelled(task_id),
                ))
                if self._cancelled(task_id):
                    return self._cancel(task_id)
                final_result = research["report"]
                update_task(
                    task_id, status="completed", current_stage="completed", progress=100,
                    result=final_result, summary=final_result,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
                log_event(task_id, "completed", "Research report saved as an artifact.")
                completed_task = get_task(task_id)
                if task.get("notify_on_completion", 1) and completed_task:
                    self._notifications.notify_task_outcome(completed_task, "completed")
                return

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
                summary=final_result,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

            log_event(
                task_id,
                "completed",
                "Task completed successfully.",
            )
            completed_task = get_task(task_id)
            if task.get("notify_on_completion", 1) and completed_task:
                self._notifications.notify_task_outcome(completed_task, "completed")

        except Exception as exc:
            current = get_task(task_id)

            coding_limit_reached = bool(
                current_step and current_step.get("tool_name") == "coding_execute"
            )
            if (
                current
                and current["retry_count"] < current["max_retries"]
                and not coding_limit_reached
                and not isinstance(exc, StepExecutorUnavailableError)
            ):
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
                failed_task = get_task(task_id)
                if current and current.get("notify_on_completion", 1) and failed_task:
                    self._notifications.notify_task_outcome(failed_task, "failed")

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

        if tool_name == "coding_execute":
            return self._execute_coding_step(step)

        log_event(step["task_id"], "tool_execution", f"Executing tool '{tool_name}'.")
        result = asyncio.run(self._registry.execute(tool_name, **arguments))
        return json.dumps(result, default=str)

    def _execute_coding_step(self, step: dict) -> str:
        """Run coding, inspect its result, and request up to three fixes."""
        task_id = step["task_id"]
        failure = None
        last_result = {}
        for attempt in range(MAX_CODING_FIX_ATTEMPTS + 1):
            try:
                arguments = asyncio.run(
                    self._coding_agent.implementation_for(step, failure=failure)
                )
            except Exception as exc:
                failure = str(exc)
                log_event(task_id, "coding_execution", f"Coder implementation failed: {failure}")
                if attempt < MAX_CODING_FIX_ATTEMPTS:
                    log_event(task_id, "coding_fix", f"Coder fix requested ({attempt + 1}/{MAX_CODING_FIX_ATTEMPTS}).")
                    continue
                raise RuntimeError("Coder failed after 3 fix attempts: " + failure) from exc
            log_event(
                task_id,
                "tool_execution",
                f"Executing coding step attempt {attempt + 1}/{MAX_CODING_FIX_ATTEMPTS + 1}.",
            )
            result = asyncio.run(self._registry.execute("coding_execute", **arguments))
            last_result = result if isinstance(result, dict) else {"result": result}
            exit_code = last_result.get("exit_code")
            timed_out = last_result.get("timed_out", False)
            stdout = str(last_result.get("stdout", ""))
            stderr = str(last_result.get("stderr", ""))
            log_event(
                task_id,
                "coding_execution",
                f"Coding command completed with exit code {exit_code}; timed_out={timed_out}; "
                f"stdout={len(stdout)} bytes; stderr={len(stderr)} bytes.",
            )
            for file_result in last_result.get("files", []):
                if isinstance(file_result, dict) and file_result.get("path"):
                    register_artifact(task_id, file_result["path"], "file")

            if not timed_out and exit_code == 0:
                return json.dumps(last_result, default=str)

            failure = json.dumps(
                {
                    "exit_code": exit_code,
                    "timed_out": timed_out,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )
            if attempt < MAX_CODING_FIX_ATTEMPTS:
                log_event(task_id, "coding_fix", f"Coder fix requested ({attempt + 1}/{MAX_CODING_FIX_ATTEMPTS}).")

        raise RuntimeError(
            "Coding command failed after 3 fix attempts: "
            + json.dumps(
                {
                    "exit_code": last_result.get("exit_code"),
                    "timed_out": last_result.get("timed_out", False),
                    "stdout": last_result.get("stdout", ""),
                    "stderr": last_result.get("stderr", ""),
                }
            )
        )

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
