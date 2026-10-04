import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend.app.api.chat import generate_chat_response
from backend.app.core.interpreter import LeonInterpreter
from backend.app.core.planner import planner_service
from backend.app.jobs.task_manager import create_task, get_task, log_event, update_task
from backend.app.jobs.task_manager import get_tasks, request_cancel
from backend.app.core.action_authority import ActionAuthority
from backend.app.core.capabilities import Capability
from backend.app.tools.system_tools import format_local_datetime, system_registry
from backend.app.tools.weather import (
    WeatherServiceError,
    extract_weather_location,
    format_current_weather,
    get_current_weather,
)
import re
import secrets
import time
from backend.app.tools.media_tools import media_registry
from backend.app.vision.screen import ScreenCaptureError, capture_screen
from backend.app.vision.service import VisionError, VisionService
from backend.app.intelligence import intelligence_core
from backend.app.memory.memory import memory_service
from backend.app.memory.profile import personal_memory_service
from backend.app.memory.profile_models import MemoryKind, PersonalMemoryCreate, MemorySource, RelationshipCreate
from backend.app.tools.system_tools import SystemStatsTool
from backend.app.intelligence.verification import verify_result
from backend.app.computer import (
    computer_controller,
    observation_service,
    get_active_window_info,
    ComputerAction,
    ComputerActionType,
)
from backend.app.missions import mission_service
from backend.app.email.providers import EmailProviderUnavailable

logger = logging.getLogger("leon.command")

router = APIRouter(prefix="/command", tags=["Command"])
interpreter = LeonInterpreter()
vision_service = VisionService()


class CommandRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    confirmed: bool = False
    confirmation_id: str | None = None


_pending_media_confirmations: dict[str, tuple[str, float]] = {}


def _issue_media_confirmation(message: str) -> str:
    confirmation_id = secrets.token_urlsafe(24)
    _pending_media_confirmations[confirmation_id] = (message, time.time() + 300)
    return confirmation_id


def _consume_media_confirmation(message: str, confirmation_id: str | None) -> bool:
    if not confirmation_id:
        return False
    pending = _pending_media_confirmations.pop(confirmation_id, None)
    if not pending:
        return False
    original, expires_at = pending
    return expires_at > time.time() and secrets.compare_digest(original, message)


def _email_arguments(message: str) -> dict[str, str] | None:
    """Parse the intentionally narrow, auditable natural-language email form."""
    address = re.search(r"\bto\s+(?P<to>[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})\b", message, re.IGNORECASE)
    if not address:
        return None
    remainder = message[address.end():].strip()
    subject_body = re.match(r"subject\s+(?P<subject>.+?)\s+body\s+(?P<body>.+)$", remainder, re.IGNORECASE | re.DOTALL)
    if not subject_body:
        return {"to": address.group("to"), "subject": "", "body": ""}
    return {
        "to": address.group("to"),
        "subject": subject_body.group("subject").strip(),
        "body": subject_body.group("body").strip(),
    }


@router.post("")
async def command(request: CommandRequest, http_request: Request = None):  # type: ignore[assignment]
    request_id = getattr(getattr(http_request, "state", None), "request_id", "unknown")
    logger.info("command_received request_id=%s message_length=%d confirmed=%s", request_id, len(request.message), request.confirmed)
    # The Intelligence Core is the front door for deterministic capability
    # selection. The legacy interpreter remains as a compatibility adapter for
    # task/weather/chat behavior that has not migrated yet.
    route = intelligence_core.route(request.message)

    # Missions are the multi-step extension of the existing task system. The
    # plan is created now; execution remains in the durable worker and every
    # tool still crosses ActionAuthority there.
    if route.intent.kind.value == "task" and route.route == "tasks.autonomous":
        mission = mission_service.create(request.message)
        await mission_service.plan(mission["id"])
        logger.info("mission_created request_id=%s mission_id=%s route=%s", request_id, mission["id"], route.route)
        return {
            "type": "mission",
            "capability": "MISSIONS",
            "action": "create",
            "message": f"Mission created: #{mission['id']}",
            "mission": mission_service.get(mission["id"]),
        }

    if route.route == "memory.local":
        handled = personal_memory_service.handle_command(request.message)
        if handled is not None:
            return {"type": "action", "capability": "MEMORY", "action": route.intent.action or "retrieve", "message": handled, "result": handled, "verified": True}
        if route.intent.action == "delete":
            target = re.sub(r"^\s*(?:forget|delete|remove)\s+(?:my\s+)?(?:memory\s+of\s+|memory\s+about\s+)?", "", request.message, flags=re.IGNORECASE).strip(" .?!")
            if target.lower() in {"name", "preferred name"} and personal_memory_service.get_profile()["profile"].preferred_name:
                personal_memory_service.update_profile({"preferred_name": None}, source=MemorySource.USER_CORRECTION)
                return {"type": "action", "capability": "MEMORY", "action": "delete", "message": "Forgot your preferred name.", "result": {"deleted": 1}, "verified": True}
            matches = personal_memory_service.list(query=target)
            removed = sum(personal_memory_service.delete(item["id"]) for item in matches)
            return {"type": "action", "capability": "MEMORY", "action": "delete", "message": "Forgot the matching memory." if removed else "I don't have a matching active memory.", "result": {"deleted": removed}, "verified": True}
        if route.intent.action == "store":
            content = re.sub(r"^\s*(?:remember|don't forget|do not forget)\s+(?:that\s+)?", "", request.message, flags=re.IGNORECASE).strip()
            name_match = re.search(r"\bmy\s+(?:preferred\s+)?name\s+is\s+(.+)$", content, re.IGNORECASE)
            relationship_match = re.match(r"(.+?)\s+is\s+my\s+(partner|girlfriend|boyfriend|friend|mentor|colleague|family|classmate|teacher)\.?$", content, re.IGNORECASE)
            if name_match:
                profile = personal_memory_service.update_profile({"preferred_name": name_match.group(1).strip(" .?!")})
                return {"type": "action", "capability": "MEMORY", "action": "store", "message": "I'll remember your preferred name.", "result": profile, "verified": True}
            if relationship_match:
                relationship = personal_memory_service.add_relationship(RelationshipCreate(name=relationship_match.group(1).strip(), relationship_type=relationship_match.group(2).lower()))
                return {"type": "action", "capability": "MEMORY", "action": "store", "message": "I'll remember that relationship.", "result": relationship, "verified": True}
            # Keep the legacy note for compatibility, while also placing an
            # explicit durable statement in the governed personal store.
            stored = memory_service.add("fact", content, importance=0.8)
            personal = personal_memory_service.add(PersonalMemoryCreate(
                memory_type=MemoryKind.FACT, category="explicit", key=content[:120],
                value=content, source=MemorySource.USER_EXPLICIT,
            ))
            intelligence_core.record_execution(route, success=bool(stored.get("id")), verification_result=bool(stored.get("id")))
            return {"type": "action", "capability": "MEMORY", "action": "store", "message": "I'll remember that.", "result": {"legacy": stored, "personal": personal}, "verified": bool(stored.get("id"))}
        context = "\n".join(filter(None, [memory_service.context_for(request.message), personal_memory_service.context_for(request.message)]))
        return {"type": "action", "capability": "MEMORY", "action": "retrieve", "message": context or "I don't have a matching memory.", "result": context, "verified": bool(context)}

    if route.route == "email.local":
        email = _email_arguments(request.message)
        if not email or not email["subject"] or not email["body"]:
            intelligence_core.record_execution(route, success=False, verification_result=False)
            return {
                "type": "clarification",
                "capability": "EMAIL",
                "action": "send",
                "message": "Please provide an email address, subject, and body. Example: send an email to person@example.com subject Meeting body The meeting is at 10 AM.",
                "verified": False,
            }
        if not request.confirmed:
            return {
                "type": "confirmation_required",
                "capability": "EMAIL",
                "action": "send",
                "message": f"Ready to send this email to {email['to']} with subject “{email['subject']}”. Confirm to send it.",
                "title": request.message,
                "email": {"to": email["to"], "subject": email["subject"]},
            }
        try:
            result = await ActionAuthority(system_registry).execute(
                "send_email", email, confirmed=True,
            )
        except (EmailProviderUnavailable, ValueError, OSError, RuntimeError) as exc:
            intelligence_core.record_execution(route, success=False, verification_result=False)
            return {"type": "failed", "capability": "EMAIL", "action": "send", "message": str(exc), "verified": False}
        intelligence_core.record_execution(route, success=bool(result.get("sent")), verification_result=bool(result.get("sent")))
        return {"type": "action", "capability": "EMAIL", "action": "send", "message": f"Email sent to {email['to']}.", "result": result, "verified": bool(result.get("sent"))}

    if route.route == "system.stats":
        stats = await ActionAuthority(system_registry).execute("system_stats", {})
        intelligence_core.record_execution(route, success=verify_result(stats), verification_result=verify_result(stats))
        return {"type": "action", "capability": "SYSTEM_STATS", "action": "current", "message": f"CPU usage is {stats['cpu_percent']}%.", "result": stats, "verified": "cpu_percent" in stats}

    if route.route == "computer.observe":
        win_info = get_active_window_info()
        disp = win_info.get("display_name") or "Desktop"
        title = win_info.get("title") or ""
        msg = f"You are currently using {disp} ({title})." if title and title != disp else f"You are currently using {disp}."
        intelligence_core.record_execution(route, success=True, verification_result=True)
        return {
            "type": "action",
            "capability": "COMPUTER_OBSERVE",
            "action": "active_app",
            "message": msg,
            "result": win_info,
            "verified": True,
        }

    if route.route == "computer.diagnose":
        diagnosis = await computer_controller.diagnose_screen(request.message)
        summary = diagnosis.get("visible_summary") or diagnosis.get("error_summary")
        app_name = diagnosis.get("active_application") or "active application"
        if summary:
            msg = f"Screen diagnosis for {app_name}: {summary}"
        else:
            msg = f"Screen diagnosis complete for {app_name}. No unhandled errors detected in visible viewport."
        intelligence_core.record_execution(route, success=True, verification_result=True)
        return {
            "type": "action",
            "capability": "SCREEN_DIAGNOSIS",
            "action": "diagnose",
            "message": msg,
            "result": diagnosis,
            "verified": True,
        }

    if route.route == "computer.act":
        if route.requires_confirmation and not request.confirmed:
            return {
                "type": "confirmation_required",
                "capability": "COMPUTER_USE",
                "action": "execute",
                "message": "Confirmation required before computer action can run.",
                "title": request.message,
            }
        action = ComputerAction(
            action_type=ComputerActionType.CLICK_TARGET if "click" in request.message.lower() else ComputerActionType.TYPE_TEXT,
            target_label=request.message,
            confirmed=request.confirmed,
        )
        res = await computer_controller.execute_loop(action, confirmed=request.confirmed)
        intelligence_core.record_execution(route, success=res.success, verification_result=res.success)
        return {
            "type": "action" if res.success else "failed",
            "capability": "COMPUTER_USE",
            "action": "execute",
            "message": res.message,
            "result": res.model_dump(),
            "verified": res.success,
        }

    if route.route == "coding.local" and route.intent.kind.value == "action":
        return {"type": "chat", "capability": "CODING", "route": route.route, "message": await generate_chat_response(request.message)}

    result = await interpreter.interpret(request.message)
    if route.route in {"system.datetime", "media.spotify", "screen.local", "desktop.applications"}:
        result = result.model_copy(update={
            "intent": "action",
            "capability": {"system.datetime": "DATETIME", "media.spotify": "MEDIA", "screen.local": "SCREEN", "desktop.applications": "SYSTEM"}[route.route],
            "action": route.intent.action,
            "title": request.message,
            "requires_confirmation": route.requires_confirmation,
        })

    if result.capability == Capability.DATETIME.value:
        payload = await ActionAuthority(system_registry).execute("get_datetime", {})
        intelligence_core.record_execution(route, success=verify_result(payload), verification_result=verify_result(payload))
        return {
            "type": "action",
            "capability": result.capability,
            "action": result.action or "current",
            "message": format_local_datetime(payload),
            "result": payload,
            "verified": True,
        }

    if result.capability == Capability.WEATHER.value:
        try:
            location = extract_weather_location(request.message)
        except WeatherServiceError as exc:
            intelligence_core.record_execution(route, success=False, verification_result=False)
            return {
                "type": "failed",
                "capability": result.capability,
                "action": result.action,
                "message": str(exc),
                "verified": False,
            }
        if not location:
            intelligence_core.record_execution(route, success=False, verification_result=False)
            return {
                "type": "clarification",
                "capability": result.capability,
                "action": result.action,
                "message": "Which city or location should I check? I do not infer your location.",
                "verified": False,
            }
        try:
            weather = await get_current_weather(location)
        except WeatherServiceError as exc:
            intelligence_core.record_execution(route, success=False, verification_result=False)
            return {
                "type": "failed",
                "capability": result.capability,
                "action": result.action,
                "message": str(exc),
                "verified": False,
            }
        intelligence_core.record_execution(route, success=True, verification_result=True)
        return {
            "type": "action",
            "capability": result.capability,
            "action": result.action,
            "message": format_current_weather(weather),
            "result": weather,
            "verified": True,
        }

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
        if re.search(r"\b(?:youtube\s*music|yt\s*music|ytmusic)\b", request.message, re.IGNORECASE):
            provider = "youtube_music"
        elif re.search(r"\bspotify\b", request.message, re.IGNORECASE):
            provider = "spotify"
        else:
            # Spotify is LEON's primary in-browser media device. YouTube
            # Music remains explicit because it uses a different adapter.
            provider = "spotify"
        if route.requires_confirmation:
            authorized = request.confirmed
            if provider == "spotify":
                authorized = authorized and _consume_media_confirmation(request.message, request.confirmation_id)
            if not authorized:
                confirmation_id = _issue_media_confirmation(request.message) if provider == "spotify" else None
                response = {"type": "confirmation_required", "capability": result.capability,
                            "action": result.action, "message": "Confirmation required before media playback changes can run.",
                            "title": result.title}
                if confirmation_id:
                    response["confirmation_id"] = confirmation_id
                return response
        volume_match = re.search(r"\bvolume\s+(?:to\s+)?(\d{1,3})\s*%?", request.message, re.IGNORECASE)
        volume = int(volume_match.group(1)) if volume_match else None
        media_result = await ActionAuthority(media_registry).execute(
            "media_control",
            {"action": result.action, "query": result.title, "volume": volume, "provider": provider},
        )
        intelligence_core.record_execution(route, success=bool(media_result.get("success")), verification_result=bool(media_result.get("success")))
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
            intelligence_core.record_execution(route, success=bool(opened.get("opened")), verification_result=bool(opened.get("opened")))
            return {"type": "action", "capability": result.capability, "action": result.action,
                    "message": f"Opened {app_name}.", "result": opened, "verified": bool(opened.get("opened"))}
        except (OSError, ValueError, PermissionError, FileNotFoundError) as exc:
            return {"type": "failed", "capability": result.capability, "action": result.action,
                    "code": "APP_NOT_FOUND", "message": str(exc), "verified": False}

    if result.capability in {"SCREEN", "OCR"}:
        try:
            data, content_type, _, _ = capture_screen()
            visual = await vision_service.analyze(data, content_type, request.message, "ocr" if result.capability == "OCR" else "screen")
            intelligence_core.record_execution(route, success=verify_result(visual), verification_result=verify_result(visual))
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
        update_task(task_id, context=f"request_id={request_id}")
        log_event(task_id, "intent", "Request classified as an executable task.")
        logger.info("task_created request_id=%s task_id=%s route=%s", request_id, task_id, route.route)
        try:
            await planner_service.generate_plan(task_id)
        except Exception as exc:
            # Do not leave a command-created task falsely queued when its
            # durable plan could not be created. The worker can still retry a
            # task only after an explicit user retry request.
            update_task(
                task_id,
                status="failed",
                current_stage="failed",
                error=str(exc),
                verification_status="failed",
            )
            log_event(task_id, "failed", "Task plan could not be generated.")
            return {
                "type": "failed",
                "capability": result.capability,
                "action": result.action,
                "message": "The task was created but could not be planned.",
                "task": get_task(task_id),
                "verified": False,
            }
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
