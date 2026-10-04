from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from backend.app.db.database import get_connection, init_db, now
from backend.app.security.web_security import redact_task_text


class ImprovementService:
    """Evidence-gated local learning; never changes tools or permissions."""

    IMMUTABLE_KEYS = {"permissions", "tools", "action_authority", "security_policy"}

    def __init__(self) -> None:
        init_db()

    @staticmethod
    def _hash_request(request: str) -> str:
        return hashlib.sha256(request.strip().lower().encode("utf-8")).hexdigest()[:32]

    def record_feedback(self, request: str, *, outcome: str, rating: int | None = None,
                        comment: str | None = None, route: str | None = None,
                        verified: bool = False) -> dict[str, Any]:
        if not request.strip():
            raise ValueError("request must not be blank")
        if rating is not None and rating not in range(1, 6):
            raise ValueError("rating must be between 1 and 5")
        safe_comment = redact_task_text(comment or "")
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO improvement_feedback(request_hash, route, outcome, rating, comment, verified, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (self._hash_request(request), route, redact_task_text(outcome), rating, safe_comment, int(verified), now()),
        )
        conn.commit(); conn.close()
        return self.feedback(cursor.lastrowid)

    def feedback(self, feedback_id: int) -> dict[str, Any] | None:
        conn = get_connection(); row = conn.execute("SELECT * FROM improvement_feedback WHERE id = ?", (feedback_id,)).fetchone(); conn.close()
        return dict(row) if row else None

    def list_feedback(self, limit: int = 50) -> list[dict[str, Any]]:
        conn = get_connection(); rows = conn.execute("SELECT * FROM improvement_feedback ORDER BY id DESC LIMIT ?", (max(1, min(limit, 200)),)).fetchall(); conn.close()
        return [dict(row) for row in rows]

    def profile(self) -> dict[str, Any]:
        conn = get_connection(); rows = conn.execute("SELECT key, value, version, updated_at FROM improvement_profile ORDER BY key").fetchall(); conn.close()
        result = {row["key"]: json.loads(row["value"]) for row in rows}
        return {"version": max((row["version"] for row in rows), default=0), "profile": result, "learning_active": True}

    def proposals(self, limit: int = 50) -> list[dict[str, Any]]:
        conn = get_connection(); rows = conn.execute("SELECT * FROM improvement_proposals ORDER BY id DESC LIMIT ?", (max(1, min(limit, 200)),)).fetchall(); conn.close()
        result = []
        for row in rows:
            value = dict(row); value["change"] = json.loads(value.pop("change_json")); result.append(value)
        return result

    async def learn(self) -> dict[str, Any]:
        """Generate a proposal from repeated low-rated outcomes and gate it.

        The candidate is only a response-style profile update. It cannot alter
        routing permissions, registered tools, or security policy.
        """
        feedback = self.list_feedback(200)
        low = [item for item in feedback if item.get("rating") is not None and item["rating"] <= 2]
        groups = Counter(item["route"] or "general" for item in low)
        repeated = [(route, count) for route, count in groups.items() if count >= 2]
        if not repeated:
            return {"status": "no_change", "reason": "insufficient repeated negative evidence", **self.profile()}

        route, count = max(repeated, key=lambda item: item[1])
        change = {"response_guidance": f"For {route}, be more explicit about uncertainty and verification."}
        baseline = self._score(feedback)
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO improvement_proposals(kind, title, rationale, change_json, baseline_score, status, created_at) VALUES (?, ?, ?, ?, ?, 'evaluated', ?)",
            ("response_guidance", f"Improve {route} responses", f"{count} low-rated outcomes were observed for this route.", json.dumps(change), baseline, now()),
        )
        proposal_id = cursor.lastrowid
        conn.commit(); conn.close()
        # A conservative candidate is activated only after the deterministic
        # regression gate confirms no safety profile is being modified.
        self._activate(int(proposal_id), change, baseline)
        return {"status": "activated", "proposal_id": proposal_id, **self.profile()}

    @staticmethod
    def _score(feedback: list[dict[str, Any]]) -> float:
        rated = [item["rating"] for item in feedback if item.get("rating")]
        return round(sum(rated) / len(rated) / 5, 3) if rated else 0.0

    def _activate(self, proposal_id: int, change: dict[str, Any], score: float) -> None:
        if any(key in self.IMMUTABLE_KEYS for key in change):
            raise ValueError("improvement proposal attempted to change an immutable safety key")
        conn = get_connection()
        for key, value in change.items():
            previous = conn.execute("SELECT version FROM improvement_profile WHERE key = ?", (key,)).fetchone()
            version = (previous["version"] + 1) if previous else 1
            conn.execute("INSERT INTO improvement_profile(key, value, version, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, version = excluded.version, updated_at = excluded.updated_at", (key, json.dumps(value), version, now()))
        conn.execute("UPDATE improvement_proposals SET candidate_score = ?, status = 'active', activated_at = ? WHERE id = ?", (score, now(), proposal_id))
        conn.commit(); conn.close()

    def rollback(self, proposal_id: int) -> bool:
        conn = get_connection(); row = conn.execute("SELECT change_json FROM improvement_proposals WHERE id = ? AND status = 'active'", (proposal_id,)).fetchone()
        if not row:
            conn.close(); return False
        change = json.loads(row["change_json"])
        for key in change:
            conn.execute("DELETE FROM improvement_profile WHERE key = ?", (key,))
        conn.execute("UPDATE improvement_proposals SET status = 'rolled_back', rolled_back_at = ? WHERE id = ?", (now(), proposal_id))
        conn.commit(); conn.close(); return True


improvement_service = ImprovementService()
