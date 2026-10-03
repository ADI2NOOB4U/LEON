from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "online",
        "service": "LEON",
        "version": "0.1.0",
    }
