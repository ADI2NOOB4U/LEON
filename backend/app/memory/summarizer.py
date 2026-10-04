def summarize(items: list[dict], limit: int = 12) -> list[dict]:
    """Return user-facing memory records without internal storage metadata."""
    return [{key: item[key] for key in ("category", "key", "value", "confidence", "privacy_level", "updated_at") if key in item} for item in items[:limit]]
