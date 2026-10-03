from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.core.interpreter import LeonInterpreter
from backend.app.jobs.task_manager import create_task, get_task

router = APIRouter(prefix="/command", tags=["Command"])
interpreter = LeonInterpreter()


class CommandRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)


@router.post("")
async def command(request: CommandRequest):
    result = await interpreter.interpret(request.message)

    if result.intent == "task":
        task_id = create_task(result.title)
        return {
            "type": "task",
            "message": f"Task created: #{task_id}",
            "task": get_task(task_id),
        }

    return {
        "type": "chat",
        "message": "Normal conversation request.",
    }
