from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.intelligence import intelligence_core

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])


class RouteInspectionRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    context: dict = Field(default_factory=dict)


@router.post("/route")
async def inspect_route(request: RouteInspectionRequest):
    """Development-safe route inspection. It never executes a capability."""
    return intelligence_core.route(request.message, request.context).diagnostic()
