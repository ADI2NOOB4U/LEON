from .profile import personal_memory_service


def list_relationships(name: str | None = None) -> list[dict]:
    return personal_memory_service.relationships(name)


def forget_relationship(person_id: str) -> bool:
    return personal_memory_service.forget_relationship(person_id)

