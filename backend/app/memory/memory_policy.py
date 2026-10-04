from .profile_models import MemorySource, PrivacyLevel


def can_promote_to_durable(*, source: MemorySource, explicit: bool, relevance: float, confidence: str) -> bool:
    """Conservative promotion gate; external content is never trusted here."""
    if source in {MemorySource.CONVERSATION_INFERENCE, MemorySource.IMPORTED, MemorySource.SYSTEM}:
        return False
    return explicit or (relevance >= 0.85 and confidence == "HIGH")


def should_inject(privacy_level: str, *, cloud: bool = False, sensitive_allowed: bool = False) -> bool:
    return privacy_level != PrivacyLevel.HIGHLY_PRIVATE.value or (not cloud and sensitive_allowed)

