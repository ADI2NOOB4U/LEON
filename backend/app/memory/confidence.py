from .profile_models import Confidence


def from_source(source: str) -> Confidence:
    return Confidence.HIGH if source in {"USER_EXPLICIT", "USER_CORRECTION", "USER_PROFILE"} else Confidence.LOW

