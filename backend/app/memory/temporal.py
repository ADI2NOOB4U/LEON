from datetime import date


def normalize_date(value: str) -> str:
    """Normalize a user-entered ISO date without using a model for arithmetic."""
    return date.fromisoformat(value).isoformat()


def classify_status(value: str) -> str:
    return value.strip().upper().replace(" ", "_")

