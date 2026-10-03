import json
from json import JSONDecodeError

from pydantic import ValidationError

from backend.app.core.router import ModelRouter
from backend.app.db.database import get_connection, now
from backend.app.jobs.task_manager import get_task
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
            existing = conn.execute(
                "SELECT id FROM task_plans WHERE task_id = ?", (task_id,)
            ).fetchone()
            if existing:
                plan_id = int(existing["id"])
                conn.execute("DELETE FROM plan_steps WHERE task_id = ?", (task_id,))
                conn.execute(
                    "UPDATE task_plans SET updated_at = ? WHERE id = ?",
                    (timestamp, plan_id),
                )
            else:
                cursor = conn.execute(
                    "INSERT INTO task_plans(task_id, created_at, updated_at) VALUES (?, ?, ?)",
                    (task_id, timestamp, timestamp),
                )
                plan_id = int(cursor.lastrowid)

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
                "content": f"Create an ordered plan for this request:\n{request}",
            },
        ]

        for attempt in range(2):
            response = await self.router.chat(messages)
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
