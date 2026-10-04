from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.improvement import improvement_service

router = APIRouter(prefix="/improvement", tags=["Self Improvement"])


class FeedbackRequest(BaseModel):
    request: str = Field(min_length=1, max_length=10000)
    outcome: str = Field(min_length=1, max_length=2000)
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=4000)
    route: str | None = Field(default=None, max_length=100)
    verified: bool = False


@router.post("/feedback")
async def record_feedback(request: FeedbackRequest):
    return improvement_service.record_feedback(**request.model_dump())


@router.get("/feedback")
async def list_feedback(limit: int = 50):
    return improvement_service.list_feedback(limit)


@router.get("/profile")
async def get_profile():
    return improvement_service.profile()


@router.get("/proposals")
async def list_proposals(limit: int = 50):
    return improvement_service.proposals(limit)


@router.post("/learn")
async def run_learning_cycle():
    return await improvement_service.learn()


@router.post("/proposals/{proposal_id}/rollback")
async def rollback_proposal(proposal_id: int):
    if not improvement_service.rollback(proposal_id):
        raise HTTPException(status_code=404, detail="Active improvement proposal not found")
    return {"status": "rolled_back", "proposal_id": proposal_id, **improvement_service.profile()}
