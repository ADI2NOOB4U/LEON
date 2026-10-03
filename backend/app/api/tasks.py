from fastapi import APIRouter, HTTPException

from backend.app.jobs.task_manager import (
    create_task,
    get_task,
    get_tasks,
    get_task_logs,
    request_cancel,
)
from backend.app.models.tasks import (
    TaskCreate,
    TaskLog,
    TaskResponse,
)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("", response_model=TaskResponse)
async def create_new_task(request: TaskCreate):
    task_id = create_task(
        request.title,
        request.max_retries,
        request.task_type,
        request.research_source_count,
        request.notify_on_completion,
        request.priority,
    )
    return get_task(task_id)


@router.get("", response_model=list[TaskResponse])
async def list_all_tasks():
    return get_tasks()


@router.get("/{task_id}", response_model=TaskResponse)
async def get_single_task(task_id: int):
    task = get_task(task_id)

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return task


@router.get("/{task_id}/logs", response_model=list[TaskLog])
async def task_logs(task_id: int):
    if not get_task(task_id):
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return get_task_logs(task_id)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: int):
    if not get_task(task_id):
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    if not request_cancel(task_id):
        raise HTTPException(
            status_code=409,
            detail="Task cannot be cancelled.",
        )

    return get_task(task_id)


from backend.app.models.schemas import PlanCreate, PlanResponse


@router.post("/{task_id}/plan", response_model=PlanResponse)
async def create_task_plan(task_id: int, request: PlanCreate | None = None):
    from backend.app.core.planner import PlanGenerationError, planner_service

    if not get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    if request is not None:
        try:
            return planner_service.create_plan(task_id, request.steps)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        return await planner_service.generate_plan(task_id)
    except PlanGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{task_id}/plan", response_model=PlanResponse)
async def get_task_plan(task_id: int):
    from backend.app.core.planner import planner_service

    if not get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    plan = planner_service.get_plan(task_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Task plan not found")
    return plan
