from fastapi import APIRouter, HTTPException, Query

from backend.app.memory.memory import memory_service
from backend.app.models.schemas import MemoryCreate, MemoryResponse


router = APIRouter(prefix="/memory", tags=["Memory"])


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
