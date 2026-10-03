from fastapi import APIRouter, HTTPException

from backend.app.config.settings import settings
from backend.app.core.agent import LeonAgent
from backend.app.security.cloud_privacy import CloudPrivacyError
from backend.app.models.schemas import ChatRequest, ChatResponse

router = APIRouter()
agent = LeonAgent()


async def generate_chat_response(message: str) -> str:
    try:
        return await agent.chat(message)
    except CloudPrivacyError as exc:
        raise HTTPException(
            status_code=403,
            detail="Cloud routing was blocked by the privacy policy.",
        ) from exc
    except RuntimeError as exc:
        message = str(exc)
        if message.startswith("Gemini is unavailable") or message.startswith("Gemini rejected"):
            raise HTTPException(status_code=503, detail=message) from exc
        raise HTTPException(
            status_code=502,
            detail="The configured model provider failed.",
        ) from exc
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status == 429:
            raise HTTPException(
                status_code=503,
                detail="Gemini unavailable: HTTP 429 (quota, rate limit, or account/project limit).",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="The configured model provider failed.",
        ) from exc


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    response = await generate_chat_response(request.message)
    return ChatResponse(assistant=response, provider=settings.model_provider)
