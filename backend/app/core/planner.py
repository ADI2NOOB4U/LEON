import json
import re
from json import JSONDecodeError

from pydantic import ValidationError

from backend.app.core.router import ModelRouter
from backend.app.db.database import get_connection, now
from backend.app.jobs.task_manager import get_task
from backend.app.memory.memory import memory_service
from backend.app.models.schemas import GeneratedPlan, PlannedStep, PlanStepStatus
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.system_tools import system_registry


class PlanGenerationError(ValueError):
    """Raised when the model cannot produce a valid structured plan."""


class PlannerService:
    """Generate and persist plans without executing their steps."""

    def __init__(
        self, router: ModelRouter | None = None, registry: ToolRegistry | None = None
    ):
        self.router = router or ModelRouter()
        self.registry = registry or system_registry

    def create_plan(self, task_id: int, steps: list[str | PlannedStep]) -> dict:
        if not get_task(task_id):
            raise ValueError("Task not found")
        if not steps:
            raise ValueError("A plan must contain at least one step")

        normalized_steps = [
            PlannedStep(
                title=step.strip(),
                description=f"Complete this part of the task: {step.strip()}",
            )
            if isinstance(step, str)
            else PlannedStep.model_validate(step, strict=True)
            for step in steps
        ]
        for step in normalized_steps:
            if step.tool_name and self.registry.get(step.tool_name) is None:
                raise ValueError(f"Unknown tool: {step.tool_name}")

        timestamp = now()
        conn = get_connection()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO task_plans(task_id, created_at, updated_at) VALUES (?, ?, ?)",
                (task_id, timestamp, timestamp),
            )
            existing = conn.execute(
                "SELECT id FROM task_plans WHERE task_id = ?", (task_id,)
            ).fetchone()
            if existing is None:
                raise PlanGenerationError("Task plan could not be created")
            plan_id = int(existing["id"])
            conn.execute("DELETE FROM plan_steps WHERE task_id = ?", (task_id,))
            conn.execute(
                "UPDATE task_plans SET updated_at = ? WHERE id = ?",
                (timestamp, plan_id),
            )

            conn.executemany(
                "INSERT INTO plan_steps(task_id, step_number, title, description, tool_name, arguments, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                [
                    (
                        task_id,
                        number,
                        step.title,
                        step.description,
                        step.tool_name,
                        json.dumps(step.arguments) if step.arguments is not None else None,
                    )
                    for number, step in enumerate(normalized_steps, 1)
                ],
            )
            conn.commit()
        finally:
            conn.close()

        return self.get_plan(task_id)

    async def generate_plan(self, task_id: int) -> dict:
        task = get_task(task_id)
        if not task:
            raise ValueError("Task not found")

        request = task["title"]
        if self._is_datetime_request(request):
            return self.create_plan(
                task_id,
                [
                    PlannedStep(
                        title="Get the current date and time",
                        description="Retrieve the current local date, time, and timezone.",
                        tool_name="get_datetime",
                        arguments={},
                    )
                ],
            )
        if self.router.provider_name == "mock":
            plan = GeneratedPlan(
                steps=[
                    PlannedStep(
                        title="Clarify the request",
                        description=f"Identify the intended outcome, constraints, and success criteria for: {request}",
                    ),
                    PlannedStep(
                        title="Plan the work",
                        description="Break the request into ordered actions and note any dependencies or information needed.",
                    ),
                    PlannedStep(
                        title="Review the result",
                        description="Check the eventual result against the request and its success criteria.",
                    ),
                ]
            )
            return self.create_plan(task_id, plan.steps)

        messages = [
            {
                "role": "system",
                "content": (
                    'Return only valid JSON with exactly one key, "steps". '
                    'Its value must be an array of 1 to 100 objects, each with '
                    'the required non-empty string keys "title" and "description". '
                    'A step may additionally include "tool_name" (a registered tool name) '
                    'and "arguments" (an object for that tool). Use only these keys. '
                    "Do not execute any step."
                ),
            },
            {
                "role": "user",
                "content": self._planning_request(request),
            },
        ]

        for attempt in range(2):
            response = await self._chat_with_role(messages, "general")
            try:
                plan = GeneratedPlan.model_validate(json.loads(response), strict=True)
                try:
                    return self.create_plan(task_id, plan.steps)
                except ValueError as exc:
                    raise PlanGenerationError(str(exc)) from exc
            except (JSONDecodeError, TypeError, ValidationError) as exc:
                if attempt == 1:
                    raise PlanGenerationError(
                        "The model did not return a valid plan after one retry."
                    ) from exc
                messages.extend(
                    [
                        {"role": "assistant", "content": response},
                        {
                            "role": "user",
                            "content": (
                                "That response was invalid. Return only JSON matching "
                                "the required schema, with no extra keys or prose."
                            ),
                        },
                    ]
                )

        raise PlanGenerationError("The model did not return a valid plan.")

    async def _chat_with_role(self, messages: list[dict[str, str]], role: str) -> str:
        """Use explicit routing while keeping small legacy test doubles compatible."""
        try:
            return await self.router.chat(messages, role=role)
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            return await self.router.chat(messages)

    @staticmethod
    def _planning_request(request: str) -> str:
        context = memory_service.context_for(request)
        if not context:
            return f"Create an ordered plan for this request:\n{request}"
        return (
            f"Create an ordered plan for this request:\n{request}\n\n"
            "Relevant remembered context:\n"
            f"{context}"
        )

    @staticmethod
    def _is_datetime_request(request: str) -> bool:
        normalized = re.sub(r"[^a-z0-9]+", " ", request.lower()).strip()
        return bool(
            re.search(r"\b(current|what is|whats|tell me)\b.*\b(date|time)\b", normalized)
            or re.search(r"\b(date|time)\b.*\b(current|now)\b", normalized)
            or "date and time" in normalized
        )

    def get_plan(self, task_id: int) -> dict | None:
        conn = get_connection()
        plan = conn.execute(
            "SELECT * FROM task_plans WHERE task_id = ?", (task_id,)
        ).fetchone()
        if not plan:
            conn.close()
            return None
        steps = conn.execute(
            "SELECT id, task_id, step_number, title, description, tool_name, arguments, status, result FROM plan_steps WHERE task_id = ? ORDER BY step_number ASC",
            (task_id,),
        ).fetchall()
        conn.close()
        result = dict(plan)
        result["steps"] = [self._decode_step(step) for step in steps]
        return result

    def get_pending_steps(self, task_id: int) -> list[dict]:
        conn = get_connection()
        steps = conn.execute(
            "SELECT id, task_id, step_number, title, description, tool_name, arguments, status, result FROM plan_steps WHERE task_id = ? AND status = 'pending' ORDER BY step_number ASC",
            (task_id,),
        ).fetchall()
        conn.close()
        return [self._decode_step(step) for step in steps]

    def update_step(
        self, step_id: int, status: PlanStepStatus | str, result: str | None = None
    ) -> dict | None:
        status = PlanStepStatus(status).value
        conn = get_connection()
        conn.execute(
            "UPDATE plan_steps SET status = ?, result = ? WHERE id = ?",
            (status, result, step_id),
        )
        conn.commit()
        step = conn.execute(
            "SELECT id, task_id, step_number, title, description, tool_name, arguments, status, result FROM plan_steps WHERE id = ?",
            (step_id,),
        ).fetchone()
        conn.close()
        return self._decode_step(step) if step else None

    @staticmethod
    def _decode_step(step) -> dict:
        result = dict(step)
        if result["arguments"] is not None:
            result["arguments"] = json.loads(result["arguments"])
        return result


planner_service = PlannerService()
