from fastapi import APIRouter, HTTPException

from backend.app.models.tasks import MissionCreate, MissionResponse, TaskLog
from backend.app.jobs.task_manager import get_task_logs
from backend.app.core.planner import planner_service
from backend.app.missions import mission_service
from backend.app.events import event_bus

router = APIRouter(prefix="/missions", tags=["Missions"])


def require_mission(mission_id: int) -> dict:
    mission = mission_service.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission


@router.post("", response_model=MissionResponse)
async def create_mission(request: MissionCreate):
    mission = mission_service.create(
        request.objective,
        max_retries=request.max_retries,
        priority=request.priority,
        notify_on_completion=request.notify_on_completion,
    )
    await mission_service.plan(mission["id"])
    return mission_service.get(mission["id"])


@router.get("", response_model=list[MissionResponse])
async def list_missions():
    return mission_service.list()


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(mission_id: int):
    return require_mission(mission_id)


@router.get("/{mission_id}/plan")
async def get_mission_plan(mission_id: int):
    require_mission(mission_id)
    plan = planner_service.get_plan(mission_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Mission plan not found")
    return plan


@router.get("/{mission_id}/logs", response_model=list[TaskLog])
async def get_mission_logs(mission_id: int):
    require_mission(mission_id)
    return get_task_logs(mission_id)


@router.get("/{mission_id}/events")
async def get_mission_events(mission_id: int, limit: int = 50):
    require_mission(mission_id)
    events = event_bus.get_recent_events(limit=max(1, min(limit, 100)), topic_filter="mission.")
    return [
        {"event_id": event.event_id, "topic": event.topic,
         "timestamp": event.timestamp, "payload": event.payload}
        for event in events
        if event.payload.get("mission_id") == mission_id
    ]


@router.post("/{mission_id}/pause", response_model=MissionResponse)
async def pause_mission(mission_id: int):
    require_mission(mission_id)
    if not mission_service.pause(mission_id):
        raise HTTPException(status_code=409, detail="Mission cannot be paused")
    return require_mission(mission_id)


@router.post("/{mission_id}/resume", response_model=MissionResponse)
async def resume_mission(mission_id: int):
    require_mission(mission_id)
    if not mission_service.resume(mission_id):
        raise HTTPException(status_code=409, detail="Mission cannot be resumed")
    return require_mission(mission_id)


@router.post("/{mission_id}/cancel", response_model=MissionResponse)
async def cancel_mission(mission_id: int):
    require_mission(mission_id)
    if not mission_service.cancel(mission_id):
        raise HTTPException(status_code=409, detail="Mission cannot be cancelled")
    return require_mission(mission_id)


@router.post("/{mission_id}/approve", response_model=MissionResponse)
async def approve_mission(mission_id: int):
    require_mission(mission_id)
    if not mission_service.approve(mission_id):
        raise HTTPException(status_code=409, detail="Mission cannot be approved")
    return require_mission(mission_id)


@router.post("/{mission_id}/retry", response_model=MissionResponse)
async def retry_mission(mission_id: int):
    require_mission(mission_id)
    if not mission_service.retry(mission_id):
        raise HTTPException(status_code=409, detail="Mission cannot be retried")
    return require_mission(mission_id)


@router.post("/{mission_id}/respond", response_model=MissionResponse)
async def respond_to_mission(mission_id: int, response: dict[str, str]):
    require_mission(mission_id)
    answer = (response.get("answer") or "").strip()
    if not answer:
        raise HTTPException(status_code=422, detail="answer is required")
    mission_service.set_context(mission_id, {"user_response": answer})
    if not mission_service.resume(mission_id):
        raise HTTPException(status_code=409, detail="Mission is not waiting for a response")
    return require_mission(mission_id)
