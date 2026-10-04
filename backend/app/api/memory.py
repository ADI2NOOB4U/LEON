from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from backend.app.memory.memory import memory_service
from backend.app.models.schemas import MemoryCreate, MemoryResponse
from backend.app.memory.profile import personal_memory_service
from backend.app.memory.profile_models import ImportantDateCreate, PersonalMemoryCreate, RelationshipCreate


router = APIRouter(prefix="/memory", tags=["Memory"])


class MemoryCorrection(BaseModel):
    memory_id: int
    value: Any


@router.post("", response_model=MemoryResponse, status_code=201)
async def add_memory(request: MemoryCreate):
    return memory_service.add(request.type, request.content, request.importance)


@router.get("", response_model=list[MemoryResponse])
async def list_memory():
    return memory_service.list()


@router.get("/search", response_model=list[MemoryResponse])
async def search_memory(q: str = Query(min_length=1, max_length=500)):
    return memory_service.search(q)


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(memory_id: int):
    if not memory_service.delete(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")


@router.get("/profile")
async def get_profile():
    return personal_memory_service.get_profile()


@router.patch("/profile")
async def update_profile(changes: dict):
    try:
        return personal_memory_service.update_profile(changes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/summary")
async def memory_summary():
    return personal_memory_service.summary()


@router.post("/remember")
async def remember_command(request: dict[str, str]):
    message = (request.get("message") or request.get("text") or "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="message is required")
    result = personal_memory_service.handle_command(message)
    if result is None:
        raise HTTPException(status_code=422, detail="The message is not a supported explicit memory command")
    return {"message": result}


@router.post("/forget")
async def forget_command(request: dict[str, str]):
    message = (request.get("message") or request.get("text") or "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="message is required")
    result = personal_memory_service.handle_command(f"forget {message}")
    return {"message": result or "I could not identify a stored memory to forget."}


@router.post("/correct")
async def correct_memory(request: MemoryCorrection):
    try:
        return personal_memory_service.correct(request.memory_id, request.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/settings")
async def update_memory_settings(changes: dict):
    try:
        return personal_memory_service.set_settings(changes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/personal")
async def list_personal_memory(
    q: str | None = Query(default=None, max_length=500),
    category: str | None = Query(default=None, max_length=100),
    confidence: str | None = Query(default=None),
    privacy: str | None = Query(default=None),
):
    return personal_memory_service.list(query=q, category=category, confidence=confidence, privacy=privacy)


@router.post("/personal", status_code=201)
async def add_personal_memory(request: PersonalMemoryCreate):
    try:
        return personal_memory_service.add(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/personal/category/{category}")
async def forget_personal_category(category: str):
    deleted = personal_memory_service.delete_category(category)
    return {"category": category, "deleted": deleted}


@router.delete("/personal/{memory_id}", status_code=204)
async def forget_personal_memory(memory_id: int):
    if not personal_memory_service.delete(memory_id):
        raise HTTPException(status_code=404, detail="Personal memory not found")
    return Response(status_code=204)


@router.get("/relationships")
async def list_relationships(name: str | None = Query(default=None, max_length=200)):
    return personal_memory_service.relationships(name)


@router.post("/relationships", status_code=201)
async def add_relationship(request: RelationshipCreate):
    try:
        return personal_memory_service.add_relationship(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/important-dates")
async def list_important_dates(include_inactive: bool = False):
    return personal_memory_service.important_dates(include_inactive=include_inactive)


@router.post("/important-dates", status_code=201)
async def add_important_date(request: ImportantDateCreate):
    try:
        return personal_memory_service.add_important_date(request)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/important-dates/{date_id}", status_code=204)
async def delete_important_date(date_id: int):
    if not personal_memory_service.forget_important_date(date_id):
        raise HTTPException(status_code=404, detail="Important date not found")
    return Response(status_code=204)


@router.post("/important-dates/{date_id}/reminder")
async def schedule_date_reminder(date_id: int, days_before: int = 7):
    try:
        return personal_memory_service.schedule_reminder(date_id, days_before)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/relationships/{person_id}", status_code=204)
async def forget_relationship(person_id: str):
    if not personal_memory_service.forget_relationship(person_id):
        raise HTTPException(status_code=404, detail="Relationship not found")
    return Response(status_code=204)


@router.get("/export")
async def export_memory():
    profile = personal_memory_service.get_profile()
    return {"profile": profile["profile"], "settings": profile["settings"], "memories": personal_memory_service.list(), "relationships": personal_memory_service.relationships()}
