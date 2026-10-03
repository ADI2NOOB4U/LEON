from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.app.config.settings import settings
from backend.app.models.schemas import VisionResponse
from backend.app.vision.service import VisionError, VisionService
from backend.app.vision.screen import ScreenCaptureError, capture_screen

router = APIRouter()
vision_service = VisionService()


@router.post("/vision/screen")
async def analyze_screen(prompt: str | None = None, mode: Literal["general", "ocr", "screen"] = "screen"):
    try:
        data, content_type, _, _ = capture_screen()
        return await vision_service.analyze(data, content_type, prompt, mode)
    except ScreenCaptureError as exc:
        raise HTTPException(status_code=503, detail={"code": str(exc), "message": "Unable to capture the screen."}) from exc
    except VisionError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc


@router.post("/vision/analyze", response_model=VisionResponse)
async def analyze_vision(image: UploadFile = File(...), prompt: str | None = Form(default=None), mode: Literal["general", "ocr", "screen", "document", "object"] = Form(default="general")) -> VisionResponse:
    content_type = (image.content_type or "").split(";", 1)[0].lower().strip()
    if content_type not in {"image/png", "image/jpeg", "image/webp"}:
        await image.close()
        raise HTTPException(status_code=415, detail={"code": "unsupported_image", "message": "Use a PNG, JPEG, or WebP image."})
    try:
        data = await image.read(int(settings.vision_max_image_mb * 1024 * 1024) + 1)
    finally:
        await image.close()
    try:
        return VisionResponse(**await vision_service.analyze(data, content_type, prompt, mode))
    except VisionError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
