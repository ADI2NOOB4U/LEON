from __future__ import annotations

import json
from typing import Any

from backend.app.jobs.task_manager import (
    create_task,
    get_task,
    get_tasks,
    log_event,
    pause_task,
    request_cancel,
    resume_task,
    retry_task,
    update_task,
    wait_for_user,
)
from backend.app.core.planner import planner_service
from backend.app.events import event_bus, EventTopic


class MissionService:
    """Thin mission facade; persistence and execution remain task-owned."""

    def create(self, objective: str, *, max_retries: int = 3,
               priority: str = "normal", notify_on_completion: bool = True) -> dict:
        mission_id = create_task(
            objective,
            max_retries=max_retries,
            task_type="mission",
            priority=priority,
            notify_on_completion=notify_on_completion,
        )
        log_event(mission_id, "mission_created", "Mission created.")
        event_bus.emit(EventTopic.MISSION_CREATED, mission_id=mission_id)
        return get_task(mission_id)

    def get(self, mission_id: int) -> dict | None:
        task = get_task(mission_id)
        return task if task and task.get("task_type") == "mission" else None

    def list(self) -> list[dict]:
        return [task for task in get_tasks() if task.get("task_type") == "mission"]

    async def plan(self, mission_id: int) -> dict:
        mission = self.get(mission_id)
        if not mission:
            raise ValueError("Mission not found")
        update_task(mission_id, status="planning", current_stage="planning")
        plan = await planner_service.generate_plan(mission_id)
        update_task(mission_id, status="queued", current_stage="ready", checkpoint="plan_created")
        log_event(mission_id, "mission_planned", "Mission plan generated.")
        event_bus.emit(EventTopic.MISSION_STARTED, mission_id=mission_id, phase="planned")
        return plan

    def set_context(self, mission_id: int, context: dict[str, Any]) -> bool:
        if not self.get(mission_id):
            return False
        update_task(mission_id, context=json.dumps(context, separators=(",", ":")))
        return True

    def pause(self, mission_id: int) -> bool:
        return pause_task(mission_id, "Mission paused at a safe checkpoint.")

    def resume(self, mission_id: int) -> bool:
        return resume_task(mission_id)

    def cancel(self, mission_id: int) -> bool:
        return request_cancel(mission_id)

    def wait(self, mission_id: int, reason: str) -> bool:
        if not self.get(mission_id):
            return False
        update_task(mission_id, status="awaiting_user", current_stage="awaiting_user", waiting_reason=reason, wait_for_user_reason=reason)
        log_event(mission_id, "mission_waiting", reason)
        event_bus.emit(EventTopic.MISSION_WAITING, mission_id=mission_id, reason=reason)
        return True

    def retry(self, mission_id: int) -> bool:
        return retry_task(mission_id)

    def approve(self, mission_id: int) -> bool:
        if not self.get(mission_id):
            return False
        update_task(mission_id, approval_granted=1, status="queued", current_stage="ready", waiting_reason=None)
        log_event(mission_id, "mission_approved", "Mission approval granted by user.")
        event_bus.emit(EventTopic.MISSION_CONFIRMATION_REQUIRED, mission_id=mission_id, approved=True)
        return True


mission_service = MissionService()
