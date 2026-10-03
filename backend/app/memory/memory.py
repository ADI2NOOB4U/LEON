from backend.app.db.database import get_connection, now
from backend.app.models.schemas import MemoryCreate, MemoryType


class MemoryService:
    def add(
        self,
        memory_type: MemoryType | str,
        content: str,
        importance: float = 0.5,
    ) -> dict:
        memory = MemoryCreate(type=memory_type, content=content, importance=importance)
        timestamp = now()
        conn = get_connection()
        cursor = conn.execute(
            """
            INSERT INTO memory(type, content, importance, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (memory.type.value, memory.content, memory.importance, timestamp, timestamp),
        )
        memory_id = int(cursor.lastrowid)
        conn.commit()
        conn.close()
        return self._get(memory_id)

    def search(self, keyword: str) -> list[dict]:
        keyword = keyword.strip()
        if not keyword:
            return []
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT * FROM memory
            WHERE content LIKE ? COLLATE NOCASE
            ORDER BY updated_at DESC, id DESC
            """,
            (f"%{keyword}%",),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def list(self) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM memory ORDER BY updated_at DESC, id DESC"
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def delete(self, memory_id: int) -> bool:
        conn = get_connection()
        cursor = conn.execute("DELETE FROM memory WHERE id = ?", (memory_id,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    @staticmethod
    def _get(memory_id: int) -> dict:
        conn = get_connection()
        row = conn.execute("SELECT * FROM memory WHERE id = ?", (memory_id,)).fetchone()
        conn.close()
        return dict(row)


memory_service = MemoryService()
