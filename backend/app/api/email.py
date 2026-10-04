from fastapi import APIRouter

from backend.app.config.settings import settings
from backend.app.email.providers import create_email_provider, UnavailableEmailProvider

router = APIRouter(prefix="/email", tags=["Email"])


@router.get("/status")
async def email_status():
    """Return non-secret Gmail readiness information."""
    provider = create_email_provider()
    configured = not isinstance(provider, UnavailableEmailProvider)
    return {
        "configured": configured,
        "provider": "gmail" if settings.email_provider.strip().lower() == "gmail" or configured else None,
        "sender_configured": bool(settings.gmail_sender.strip()),
        "requires_confirmation": True,
        "credentials_exposed": False,
    }
