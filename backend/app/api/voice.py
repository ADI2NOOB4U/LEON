from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.api.chat import agent
from backend.app.models.schemas import VoiceTurnResponse
from backend.app.voice.service import MAX_AUDIO_BYTES, LeonVoiceService, VoiceServiceError


router = APIRouter()
voice_service = LeonVoiceService(agent)

_AUDIO_SUFFIXES = {
    "audio/webm": ".webm",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/ogg": ".ogg",
    "audio/mp4": ".mp4",
    "audio/mpeg": ".mp3",
}


@router.post("/voice/turn", response_model=VoiceTurnResponse)
async def voice_turn(audio: UploadFile = File(...)) -> VoiceTurnResponse:
    content_type = (audio.content_type or "").split(";", maxsplit=1)[0].lower()
    suffix = _AUDIO_SUFFIXES.get(content_type)
    if suffix is None:
        await audio.close()
        raise HTTPException(
            status_code=415,
            detail="Unsupported audio format. Use WebM, WAV, OGG, MP4, or MP3.",
        )

    try:
        recording = await audio.read(MAX_AUDIO_BYTES + 1)
    finally:
        await audio.close()

    try:
        return await voice_service.process(recording, suffix)
    except VoiceServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
