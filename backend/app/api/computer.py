from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.computer.controller import computer_controller
from backend.app.computer.schemas import (
    ComputerAction,
    ComputerState,
    ExecutionResult,
    Observation,
)
from backend.app.computer.windows import get_active_window_info, list_running_applications

router = APIRouter(prefix="/computer", tags=["Computer Use"])


class ObserveRequest(BaseModel):
    include_vision: bool = True
    prompt: Optional[str] = None
    mode: str = "screen"


class DiagnoseRequest(BaseModel):
    question: Optional[str] = None


class ActRequest(BaseModel):
    action: ComputerAction
    confirmed: bool = False
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)


@router.post("/observe", response_model=Observation)
async def observe_screen(request: ObserveRequest = ObserveRequest()):
    try:
        return await computer_controller.observe_current_state(
            include_vision=request.include_vision,
            prompt=request.prompt,
            mode=request.mode,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/diagnose")
async def diagnose_screen(request: DiagnoseRequest = DiagnoseRequest()):
    try:
        return await computer_controller.diagnose_screen(question=request.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/act", response_model=ExecutionResult)
async def execute_computer_action(request: ActRequest):
    return await computer_controller.execute_loop(
        action=request.action,
        confirmed=request.confirmed,
        timeout_seconds=request.timeout_seconds,
    )


@router.post("/cancel")
async def cancel_computer_action():
    computer_controller.cancel()
    return {"status": "cancelled", "state": computer_controller.state}


@router.get("/status")
async def computer_status():
    win_info = get_active_window_info()
    running_apps = list_running_applications()
    return {
        "state": computer_controller.state,
        "active_application": win_info.get("display_name"),
        "active_window": win_info.get("title"),
        "running_applications": running_apps,
    }
