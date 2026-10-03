from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.api.chat import generate_chat_response
from backend.app.core.interpreter import LeonInterpreter
from backend.app.core.planner import planner_service
from backend.app.jobs.task_manager import create_task, get_task, log_event
from backend.app.jobs.task_manager import get_tasks, request_cancel
from backend.app.core.action_authority import ActionAuthority
from backend.app.tools.system_tools import system_registry
import re
from backend.app.tools.media_tools import media_registry
from backend.app.vision.screen import ScreenCaptureError, capture_screen
from backend.app.vision.service import VisionError, VisionService

router = APIRouter(prefix="/command", tags=["Command"])
interpreter = LeonInterpreter()
vision_service = VisionService()


class CommandRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    confirmed: bool = False


@router.post("")
async def command(request: CommandRequest):
    result = await interpreter.interpret(request.message)

    if result.capability == "TASKS" and result.action == "list":
        tasks = get_tasks()[:10]
        return {"type": "action", "capability": result.capability, "action": result.action,
                "message": f"Found {len(tasks)} recent task(s).", "tasks": tasks, "verified": True}
    if result.capability == "TASKS" and result.action == "cancel":
        active = next((task for task in get_tasks() if task["status"] in {"queued", "running", "executing", "planning", "verifying"}), None)
        if not active:
            return {"type": "action", "capability": result.capability, "action": result.action,
                    "message": "There is no active task to cancel.", "verified": True}
        request_cancel(active["id"])
        return {"type": "action", "capability": result.capability, "action": result.action,
                "message": f"Cancellation requested for task #{active['id']}.", "task": get_task(active["id"]), "verified": True}

    if result.capability == "MEDIA":
        volume_match = re.search(r"\bvolume\s+(?:to\s+)?(\d{1,3})\s*%?", request.message, re.IGNORECASE)
        volume = int(volume_match.group(1)) if volume_match else None
        media_result = await ActionAuthority(media_registry).execute(
            "media_control",
            {"action": result.action, "query": result.title, "volume": volume},
        )
        return {
            "type": "action" if media_result.get("success") else "failed",
            "capability": result.capability,
            "action": result.action,
            "message": media_result.get("message") or ("Media action completed." if media_result.get("success") else "Media action failed."),
            "result": media_result,
            "verified": bool(media_result.get("success")),
        }

    if result.capability == "SYSTEM" and result.action == "open" and request.confirmed:
        match = re.search(r"\b(?:open|launch|start)\s+(.+?)[.!?]*$", request.message, re.IGNORECASE)
        app_name = (match.group(1).strip() if match else "")
        try:
            opened = await ActionAuthority(system_registry).execute("open_app", {"app_name": app_name}, confirmed=True)
            return {"type": "action", "capability": result.capability, "action": result.action,
                    "message": f"Opened {app_name}.", "result": opened, "verified": bool(opened.get("opened"))}
        except (OSError, ValueError, PermissionError, FileNotFoundError) as exc:
            return {"type": "failed", "capability": result.capability, "action": result.action,
                    "code": "APP_NOT_FOUND", "message": str(exc), "verified": False}

    if result.capability in {"SCREEN", "OCR"}:
        try:
            data, content_type, _, _ = capture_screen()
            visual = await vision_service.analyze(data, content_type, request.message, "ocr" if result.capability == "OCR" else "screen")
            return {"type": "action", "capability": result.capability, "action": result.action,
                    "message": "Screen analysis complete.", "result": visual, "verified": True}
        except ScreenCaptureError as exc:
            return {"type": "failed", "capability": result.capability, "action": result.action,
                    "code": str(exc), "message": "Unable to capture the screen.", "verified": False}
        except VisionError as exc:
            return {"type": "failed", "capability": result.capability, "action": result.action,
                    "code": exc.code, "message": str(exc), "verified": False}

    if result.requires_confirmation and not request.confirmed:
        return {"type": "confirmation_required", "capability": result.capability,
                "action": result.action, "message": "Confirmation required before this action can run.",
                "title": result.title}

    if result.intent == "task":
        task_id = create_task(result.title, task_type=result.task_type)
        log_event(task_id, "intent", "Request classified as an executable task.")
        await planner_service.generate_plan(task_id)
        log_event(task_id, "planned", "Task plan generated.")
        return {
            "type": "task",
            "capability": result.capability,
            "action": result.action,
            "message": f"Task created: #{task_id}",
            "task": get_task(task_id),
        }

    return {
        "type": "chat",
        "message": await generate_chat_response(request.message),
    }
