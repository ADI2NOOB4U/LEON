from .profile import personal_memory_service


def correct(memory_id: int, replacement) -> dict:
    return personal_memory_service.correct(memory_id, replacement)
