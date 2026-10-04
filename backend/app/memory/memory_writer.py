from .profile import personal_memory_service
from .profile_models import PersonalMemoryCreate


def write(request: PersonalMemoryCreate) -> dict:
    return personal_memory_service.add(request)

