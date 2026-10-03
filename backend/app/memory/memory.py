import re
import sqlite3

from backend.app.db.database import get_connection, now
from backend.app.models.schemas import MemoryCreate, MemoryType


_SEARCH_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "please",
    "tell", "that", "the", "this", "to", "what", "when", "where", "who", "with",
    "you", "your",
}


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
        try:
            rows = conn.execute(
                """
                SELECT * FROM memory
                WHERE content LIKE ? COLLATE NOCASE
                ORDER BY updated_at DESC, id DESC
                """,
                (f"%{keyword}%",),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table: memory" not in str(exc):
                raise
            rows = []
        conn.close()
        return [dict(row) for row in rows]

    def retrieve_relevant(
        self, request: str, limit: int = 5, max_chars: int = 2400
    ) -> list[dict]:
        """Return bounded, SQLite-searched memories relevant to a request."""
        if limit < 1 or max_chars < 1:
            return []

        terms = [
            term
            for term in re.findall(r"[a-z0-9]+", request.lower())
            if len(term) > 1 and term not in _SEARCH_STOPWORDS
        ]
        if not terms:
            return []

        candidates: dict[int, dict] = {}
        for term in dict.fromkeys(terms):
            for memory in self.search(term):
                candidates.setdefault(int(memory["id"]), memory)

        ranked = []
        for memory in candidates.values():
            content = memory["content"].lower()
            matched_terms = sum(term in content for term in set(terms))
            if matched_terms:
                ranked.append(
                    (
                        matched_terms,
                        float(memory["importance"]),
                        memory["updated_at"],
                        int(memory["id"]),
                        memory,
                    )
                )
        ranked.sort(key=lambda item: item[:4], reverse=True)

        selected = []
        used_chars = 0
        for _, _, _, _, memory in ranked[:limit]:
            item = {"type": memory["type"], "content": memory["content"]}
            item_chars = len(item["type"]) + len(item["content"]) + 4
            separator_chars = 1 if selected else 0
            if used_chars + separator_chars + item_chars > max_chars:
                continue
            remaining = max_chars - used_chars - separator_chars
            if item_chars > remaining:
                item["content"] = item["content"][: max(1, remaining - len(item["type"]) - 4)]
            selected.append(item)
            used_chars += separator_chars + len(item["type"]) + len(item["content"]) + 4
        return selected

    def context_for(self, request: str, limit: int = 5, max_chars: int = 2400) -> str:
        return "\n".join(
            f"- {memory['type']}: {memory['content']}"
            for memory in self.retrieve_relevant(request, limit, max_chars)
        )

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
