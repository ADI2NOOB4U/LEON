from backend.app.core.router import ModelRouter


def select_model_role(route: str) -> str | None:
    return {"chat.general": "general", "coding.local": "coding", "vision.local": "vision", "screen.local": "vision", "research.current": "research"}.get(route)


def provider_available(role: str) -> bool:
    return role in {"general", "coding", "vision", "research", "embedding"}
