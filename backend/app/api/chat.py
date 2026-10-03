from fastapi import APIRouter, HTTPException

from backend.app.config.settings import settings
from backend.app.core.agent import LeonAgent
from backend.app.models.schemas import ChatRequest, ChatResponse

router = APIRouter()
agent = LeonAgent()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):

    try:
        response = await agent.chat(request.message)

        return ChatResponse(
            assistant=response,
            provider=settings.model_provider,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc
