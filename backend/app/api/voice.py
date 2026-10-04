import logging

from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from backend.app.api.chat import agent
from backend.app.models.schemas import VoiceSpeechRequest, VoiceTurnResponse
from backend.app.voice.service import MAX_AUDIO_BYTES, LeonVoiceService, VoiceServiceError


router = APIRouter()
voice_service = LeonVoiceService(agent)
logger = logging.getLogger(__name__)

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
    content_type = (audio.content_type or "").split(";", maxsplit=1)[0].strip().lower()
    suffix = _AUDIO_SUFFIXES.get(content_type)
    if suffix is None:
        await audio.close()
        raise HTTPException(
            status_code=415,
            detail={
                "code": "unsupported_audio_type",
                "message": "Unsupported audio format. Use WebM, WAV, OGG, MP4, or MP3.",
            },
        )

    try:
        recording = await audio.read(MAX_AUDIO_BYTES + 1)
    finally:
        await audio.close()

    logger.info(
        "Voice upload received (mime_type=%s, extension=%s, bytes=%d).",
        content_type,
        suffix,
        len(recording),
    )
    if len(recording) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "audio_too_large",
                "message": "The recording is too large (25 MB maximum).",
            },
        )

    try:
        return await voice_service.process(recording, suffix)
    except VoiceServiceError as exc:
        if exc.diagnostic:
            logger.warning(
                "Voice request failed (mime_type=%s, extension=%s, bytes=%d, "
                "code=%s, decoder_error=%s).",
                content_type,
                suffix,
                len(recording),
                exc.code,
                exc.diagnostic,
            )
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.post("/voice/speech")
async def synthesize_speech(request: VoiceSpeechRequest) -> Response:
    try:
        speech = await voice_service.synthesize_text(request.text)
    except VoiceServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    return Response(content=speech, media_type="audio/wav")
