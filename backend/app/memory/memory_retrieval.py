from .profile import personal_memory_service


def retrieve_relevant(request: str, limit: int = 8) -> list[dict]:
    return personal_memory_service.retrieve(request, limit=limit)


def context_for(request: str, max_chars: int = 2400) -> str:
    return personal_memory_service.context_for(request, max_chars=max_chars)

