from .profile import personal_memory_service


class MemoryStore:
    """Stable facade over LEON's single SQLite-backed memory architecture."""
    add = staticmethod(personal_memory_service.add)
    list = staticmethod(personal_memory_service.list)
    retrieve = staticmethod(personal_memory_service.retrieve)
    delete = staticmethod(personal_memory_service.delete)


memory_store = MemoryStore()

