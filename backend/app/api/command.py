from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.core.interpreter import LeonInterpreter
from backend.app.core.planner import planner_service
from backend.app.jobs.task_manager import create_task, get_task, log_event

router = APIRouter(prefix="/command", tags=["Command"])
interpreter = LeonInterpreter()


class CommandRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)


@router.post("")
async def command(request: CommandRequest):
    result = await interpreter.interpret(request.message)

    if result.intent == "task":
        task_id = create_task(result.title)
        log_event(task_id, "intent", "Request classified as an executable task.")
        await planner_service.generate_plan(task_id)
        log_event(task_id, "planned", "Task plan generated.")
        return {
            "type": "task",
            "message": f"Task created: #{task_id}",
            "task": get_task(task_id),
        }

    return {
        "type": "chat",
        "message": "Normal conversation request.",
    }
