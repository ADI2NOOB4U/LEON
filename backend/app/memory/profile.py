from __future__ import annotations

import json
import re
from typing import Any

from backend.app.db.database import get_connection, init_db, now
from backend.app.events import event_bus
from backend.app.memory.models import EntityType, KnowledgeEntityCreate, KnowledgeRelationCreate, RelationType
from backend.app.memory.profile_models import (
    Confidence, MemoryKind, MemorySource, PersonalMemoryCreate, PrivacyLevel,
    ImportantDateCreate, RelationshipCreate, Retention, UserProfile,
)
from backend.app.memory.privacy import assert_safe_memory


class PersonalMemoryService:
    def __init__(self) -> None:
        init_db()
        self._ensure_profile()

    def _ensure_profile(self) -> None:
        conn = get_connection()
        if not conn.execute("SELECT 1 FROM user_profile WHERE id = 1").fetchone():
            ts = now()
            conn.execute("INSERT INTO user_profile(id, data, settings, created_at, updated_at) VALUES (1, '{}', '{}', ?, ?)", (ts, ts))
            conn.commit()
        conn.close()

    def get_profile(self) -> dict[str, Any]:
        self._ensure_profile()
        conn = get_connection()
        row = conn.execute("SELECT data, settings, updated_at FROM user_profile WHERE id = 1").fetchone()
        conn.close()
        return {"profile": UserProfile.model_validate(json.loads(row["data"])), "settings": json.loads(row["settings"]), "updated_at": row["updated_at"]}

    def update_profile(self, changes: dict[str, Any], source: MemorySource = MemorySource.USER_EXPLICIT) -> dict[str, Any]:
        assert_safe_memory(changes)
        current = self.get_profile()["profile"].model_dump()
        for key, value in changes.items():
            if key not in current:
                raise ValueError(f"Unknown profile field: {key}")
            current[key] = value
        validated = UserProfile.model_validate(current)
        ts = now()
        conn = get_connection()
        conn.execute("UPDATE user_profile SET data = ?, updated_at = ? WHERE id = 1", (json.dumps(validated.model_dump()), ts))
        conn.commit()
        conn.close()
        self._audit("PROFILE_UPDATED", None, "profile", source.value)
        return self.get_profile()

    def set_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        allowed = {"auto_learn", "ask_before_remembering", "allow_inferred_preferences", "allow_relationship_memory", "allow_astrology_memory", "allow_proactive_personalization", "allow_sensitive_memory"}
        if set(settings) - allowed:
            raise ValueError("Unknown memory setting")
        conn = get_connection()
        existing = json.loads(conn.execute("SELECT settings FROM user_profile WHERE id = 1").fetchone()[0])
        existing.update(settings)
        conn.execute("UPDATE user_profile SET settings = ?, updated_at = ? WHERE id = 1", (json.dumps(existing), now()))
        conn.commit(); conn.close()
        return self.get_profile()

    def add(self, request: PersonalMemoryCreate) -> dict[str, Any]:
        assert_safe_memory(request.value)
        if request.source not in {MemorySource.USER_EXPLICIT, MemorySource.USER_CORRECTION, MemorySource.USER_PROFILE, MemorySource.IMPORTED}:
            raise ValueError("Durable personal memory requires a trusted user-authorized source")
        conn = get_connection(); ts = now()
        previous = conn.execute("SELECT * FROM personal_memories WHERE category = ? AND key = ? AND active = 1 ORDER BY id DESC LIMIT 1", (request.category, request.key)).fetchone()
        if previous and json.loads(previous["value"]) == request.value:
            conn.close(); return dict(previous)
        if previous:
            conn.execute("UPDATE personal_memories SET active = 0, updated_at = ? WHERE id = ?", (ts, previous["id"]))
        cursor = conn.execute("""INSERT INTO personal_memories(memory_type, category, key, value, source, confidence, privacy_level, retention, created_at, updated_at, last_confirmed, active, supersedes_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""", (request.memory_type.value, request.category, request.key, json.dumps(request.value), request.source.value, request.confidence.value, request.privacy_level.value, request.retention.value, ts, ts, ts, previous["id"] if previous else None))
        memory_id = int(cursor.lastrowid); conn.commit(); conn.close()
        self._audit("MEMORY_CORRECTED" if previous else "MEMORY_CREATED", memory_id, request.category, request.key)
        self._sync_graph_for_memory(request)
        return self.get_memory(memory_id)

    @staticmethod
    def _sync_graph_for_memory(request: PersonalMemoryCreate) -> None:
        """Mirror explicit project/preference facts into the existing graph."""
        try:
            from backend.app.memory.knowledge import knowledge_service
            from backend.app.memory.models import EntityType, KnowledgeEntityCreate, KnowledgeFactCreate, FactType
            if request.memory_type == MemoryKind.PROJECT:
                value = request.value if isinstance(request.value, dict) else {"name": str(request.value)}
                name = str(value.get("name") or request.key)
                knowledge_service.add_entity(KnowledgeEntityCreate(name=name, entity_type=EntityType.PROJECT, metadata={"source": request.source.value}))
                knowledge_service.add_fact(KnowledgeFactCreate(entity_name=name, fact_type=FactType.STATE, statement=json.dumps(value), source=request.source.value, confidence=1.0, importance=0.8))
            elif request.memory_type == MemoryKind.PREFERENCE:
                knowledge_service.add_entity(KnowledgeEntityCreate(name=request.key, entity_type=EntityType.PREFERENCE, metadata={"source": request.source.value}))
        except Exception:
            # Graph mirroring is additive and must never block durable memory.
            return

    def correct(self, memory_id: int, replacement: Any) -> dict[str, Any]:
        current = self.get_memory(memory_id)
        if not current:
            raise ValueError("Personal memory not found")
        return self.add(PersonalMemoryCreate(
            memory_type=MemoryKind(current["memory_type"]),
            category=current["category"],
            key=current["key"],
            value=replacement,
            source=MemorySource.USER_CORRECTION,
            confidence=Confidence.HIGH,
            privacy_level=PrivacyLevel(current["privacy_level"]),
            retention=Retention(current["retention"]),
        ))

    def get_memory(self, memory_id: int) -> dict[str, Any] | None:
        conn = get_connection(); row = conn.execute("SELECT * FROM personal_memories WHERE id = ?", (memory_id,)).fetchone(); conn.close()
        return self._decode(row) if row else None

    def list(self, *, query: str | None = None, category: str | None = None, confidence: str | None = None, privacy: str | None = None, include_inactive: bool = False) -> list[dict[str, Any]]:
        clauses = [] if include_inactive else ["active = 1"]; params: list[Any] = []
        if query: clauses.append("(key LIKE ? COLLATE NOCASE OR value LIKE ? COLLATE NOCASE)"); params += [f"%{query}%", f"%{query}%"]
        if category: clauses.append("category = ?"); params.append(category)
        if confidence: clauses.append("confidence = ?"); params.append(confidence)
        if privacy: clauses.append("privacy_level = ?"); params.append(privacy)
        sql = "SELECT * FROM personal_memories" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY updated_at DESC, id DESC"
        conn = get_connection(); rows = conn.execute(sql, params).fetchall(); conn.close()
        return [self._decode(row) for row in rows]

    def retrieve(self, request: str, limit: int = 8) -> list[dict[str, Any]]:
        terms = set(re.findall(r"[a-z0-9]+", request.lower())) - {"the", "my", "what", "is", "about", "tell", "me", "do", "you", "remember"}
        items = self.list(); ranked = []
        for item in items:
            haystack = f"{item['category']} {item['key']} {json.dumps(item['value'])}".lower()
            score = sum(term in haystack for term in terms)
            if score: ranked.append((score, item["confidence"] == "HIGH", item["updated_at"], item))
        ranked.sort(key=lambda row: row[:3], reverse=True)
        return [row[3] for row in ranked[:limit]]

    def delete(self, memory_id: int) -> bool:
        conn = get_connection(); changed = conn.execute("UPDATE personal_memories SET active = 0, updated_at = ? WHERE id = ? AND active = 1", (now(), memory_id)).rowcount; conn.commit(); conn.close()
        if changed: self._audit("MEMORY_DELETED", memory_id, None, None)
        return bool(changed)

    def delete_category(self, category: str) -> int:
        items = self.list(category=category)
        return sum(self.delete(item["id"]) for item in items)

    def delete_all(self) -> dict[str, int]:
        conn = get_connection(); ts = now()
        memories = conn.execute("SELECT id FROM personal_memories WHERE active = 1").fetchall()
        relationships = conn.execute("SELECT person_id FROM relationships WHERE active = 1").fetchall()
        dates = conn.execute("SELECT id FROM important_dates WHERE active = 1").fetchall()
        conn.execute("UPDATE personal_memories SET active = 0, updated_at = ? WHERE active = 1", (ts,))
        conn.execute("UPDATE relationships SET active = 0, updated_at = ? WHERE active = 1", (ts,))
        conn.execute("UPDATE important_dates SET active = 0, updated_at = ? WHERE active = 1", (ts,))
        conn.execute("UPDATE user_profile SET data = '{}', updated_at = ? WHERE id = 1", (ts,))
        conn.commit(); conn.close()
        self._audit("MEMORY_DELETED_ALL", None, None, None)
        return {"memories": len(memories), "relationships": len(relationships), "important_dates": len(dates)}

    def add_relationship(self, request: RelationshipCreate) -> dict[str, Any]:
        assert_safe_memory(request.model_dump())
        person_id = re.sub(r"[^a-z0-9]+", "-", request.name.lower()).strip("-")
        conn = get_connection(); ts = now()
        conn.execute("""INSERT INTO relationships(person_id, name, relationship_type, important_dates, preferences, notes, source, confidence, privacy_level, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?) ON CONFLICT(person_id) DO UPDATE SET name=excluded.name, relationship_type=excluded.relationship_type, important_dates=excluded.important_dates, preferences=excluded.preferences, notes=excluded.notes, confidence=excluded.confidence, privacy_level=excluded.privacy_level, active=1, updated_at=excluded.updated_at""", (person_id, request.name, request.relationship_type, json.dumps(request.important_dates), json.dumps(request.preferences), request.notes, MemorySource.USER_EXPLICIT.value, request.confidence.value, request.privacy_level.value, ts, ts))
        conn.commit(); row = conn.execute("SELECT * FROM relationships WHERE person_id = ?", (person_id,)).fetchone(); conn.close()
        try:
            from backend.app.memory.knowledge import knowledge_service
            from backend.app.memory.models import EntityType, KnowledgeEntityCreate
            knowledge_service.add_entity(KnowledgeEntityCreate(name=request.name, entity_type=EntityType.PERSON, metadata={"relationship_type": request.relationship_type}))
        except Exception:
            pass
        return self._relationship(row)

    def relationships(self, name: str | None = None) -> list[dict[str, Any]]:
        conn = get_connection(); rows = conn.execute("SELECT * FROM relationships WHERE active = 1" + (" AND name LIKE ? COLLATE NOCASE" if name else "") + " ORDER BY name", ((f"%{name}%",) if name else ())).fetchall(); conn.close()
        return [self._relationship(row) for row in rows]

    def forget_relationship(self, person_id: str) -> bool:
        conn = get_connection(); changed = conn.execute("UPDATE relationships SET active = 0, updated_at = ? WHERE person_id = ? AND active = 1", (now(), person_id)).rowcount; conn.commit(); conn.close(); return bool(changed)

    def add_important_date(self, request: ImportantDateCreate) -> dict[str, Any]:
        assert_safe_memory(request.model_dump())
        # ISO dates are deliberately validated by the API/service boundary;
        # natural-language dates must be normalized before reaching storage.
        from datetime import date
        normalized = date.fromisoformat(request.date_value).isoformat()
        conn = get_connection(); ts = now()
        conn.execute("UPDATE important_dates SET active = 0, updated_at = ? WHERE name = ? AND active = 1", (ts, request.name))
        cursor = conn.execute("""INSERT INTO important_dates(name, date_value, time_value, date_type, person_id, notes, source, confidence, privacy_level, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""", (request.name, normalized, request.time_value, request.date_type, request.person_id, request.notes, MemorySource.USER_EXPLICIT.value, request.confidence.value, request.privacy_level.value, ts, ts))
        date_id = int(cursor.lastrowid); conn.commit(); conn.close()
        self._audit("MEMORY_CREATED", date_id, "IMPORTANT_DATE", request.name)
        return self.important_date(date_id)

    def important_date(self, date_id: int) -> dict[str, Any] | None:
        conn = get_connection(); row = conn.execute("SELECT * FROM important_dates WHERE id = ?", (date_id,)).fetchone(); conn.close()
        return dict(row) if row else None

    def important_dates(self, *, include_inactive: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM important_dates" + ("" if include_inactive else " WHERE active = 1") + " ORDER BY date_value, name"
        conn = get_connection(); rows = conn.execute(sql).fetchall(); conn.close()
        return [dict(row) for row in rows]

    def forget_important_date(self, date_id: int) -> bool:
        conn = get_connection(); changed = conn.execute("UPDATE important_dates SET active = 0, updated_at = ? WHERE id = ? AND active = 1", (now(), date_id)).rowcount; conn.commit(); conn.close()
        if changed: self._audit("MEMORY_DELETED", date_id, "IMPORTANT_DATE", None)
        return bool(changed)

    def schedule_reminder(self, date_id: int, days_before: int = 7) -> dict[str, Any]:
        item = self.important_date(date_id)
        if not item or not item.get("active"):
            raise ValueError("Important date not found")
        if days_before < 0 or days_before > 3650:
            raise ValueError("days_before must be between 0 and 3650")
        from datetime import date, datetime, time, timedelta, timezone
        from backend.app.jobs.scheduler import scheduler
        run_at = datetime.combine(date.fromisoformat(item["date_value"]), time(9), tzinfo=timezone.utc) - timedelta(days=days_before)
        job = scheduler.schedule_once(
            name=f"Memory reminder: {item['name']}",
            run_at=run_at,
            payload={"type": "notification", "title": f"Upcoming: {item['name']}", "body": f"{item['name']} is on {item['date_value']}."},
        )
        return {"date": item, "scheduled_job": job}

    def context_for(self, request: str, max_chars: int = 2400) -> str:
        parts = []
        profile = self.get_profile()["profile"]
        query = request.lower()
        if any(term in query for term in ("my name", "call me", "who am i")) and profile.preferred_name:
            parts.append(f"- identity.preferred_name: {profile.preferred_name}")
        if any(term in query for term in ("work", "job", "career", "study", "education", "project", "goal")):
            for key in ("work", "education", "career", "skills", "projects", "goals"):
                if getattr(profile, key):
                    parts.append(f"- profile.{key}: {getattr(profile, key)}")
        for item in self.retrieve(request):
            if item["privacy_level"] == PrivacyLevel.HIGHLY_PRIVATE.value:
                continue
            parts.append(f"- {item['category']}.{item['key']}: {item['value']}")
        if any(term in query for term in ("partner", "girlfriend", "boyfriend", "friend", "brother", "sister", "mother", "father", "teacher", "mentor", "colleague", "who is")):
            for person in self.relationships():
                if person["privacy_level"] != PrivacyLevel.HIGHLY_PRIVATE.value:
                    parts.append(f"- relationship.{person['name']}: {person['relationship_type']}")
        if any(term in query for term in ("birthday", "anniversary", "deadline", "important date", "exam")):
            for date_item in self.important_dates():
                if date_item["privacy_level"] != PrivacyLevel.HIGHLY_PRIVATE.value:
                    parts.append(f"- important_date.{date_item['name']}: {date_item['date_value']}")
        return "\n".join(parts)[:max_chars]

    def summary(self) -> dict[str, Any]:
        profile = self.get_profile()["profile"].model_dump(exclude_none=True)
        return {
            "identity": {key: profile[key] for key in ("preferred_name", "date_of_birth", "location", "timezone", "languages") if key in profile and profile[key]},
            "work_education": {key: profile[key] for key in ("education", "work", "career", "skills") if profile.get(key)},
            "projects": profile.get("projects", []),
            "goals": profile.get("goals", []),
            "preferences": {key: profile[key] for key in ("preferences", "communication_style") if profile.get(key)},
            "important_people": [{"name": item["name"], "relationship_type": item["relationship_type"]} for item in self.relationships()],
            "important_dates": [{"name": item["name"], "date_value": item["date_value"], "date_type": item["date_type"]} for item in self.important_dates()],
            "astrology": profile.get("astrology_profile", {}),
            "memories": [{"category": item["category"], "key": item["key"], "value": item["value"], "confidence": item["confidence"]} for item in self.list()[:20]],
        }

    def handle_command(self, text: str) -> str | None:
        """Handle only obvious, user-authored memory commands deterministically."""
        raw = (text or "").strip()
        value = raw.lower()
        if not raw:
            return None

        reminder = re.search(r"\bremind me\s+(?:a\s+)?(?:week|7 days)\s+before\b", value)
        if reminder:
            dates = self.important_dates()
            if len(dates) == 1:
                self.schedule_reminder(dates[0]["id"], 7)
                return f"Scheduled a reminder one week before {dates[0]['name']}."
            return "Which important date should I remind you about?"

        no_longer = re.match(r"^(.+?)\s+is no longer my\s+([a-z ]+?)[.!?]*$", raw, re.I)
        if no_longer:
            name = no_longer.group(1).strip()
            person_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            if self.forget_relationship(person_id):
                return f"Updated: {name} is no longer stored as your {no_longer.group(2).strip()}."
            return f"I do not have an active relationship stored for {name}."

        forget_all = re.search(r"\bforget\s+(?:everything|all)\s+(?:about\s+)?(?:me|my personal memory)\b", value)
        if forget_all:
            result = self.delete_all()
            return f"Forgot your stored personal memory ({sum(result.values())} records removed)."

        if re.search(r"\b(?:forget|delete|remove)\b", value):
            if re.search(r"\b(?:my\s+)?(?:name|preferred name)\b", value):
                profile = self.get_profile()["profile"]
                if profile.preferred_name:
                    self.update_profile({"preferred_name": None}, source=MemorySource.USER_CORRECTION)
                    return "Forgot your preferred name."
                return "I do not currently have your name stored."
            target = re.sub(r"^\s*(?:forget|delete|remove)\s+(?:my\s+)?(?:memory\s+(?:of|about)\s+)?", "", raw, flags=re.I).strip(" .?!")
            matches = self.list(query=target)
            removed = sum(self.delete(item["id"]) for item in matches)
            if not removed:
                person_matches = self.relationships(target)
                removed = sum(self.forget_relationship(item["person_id"]) for item in person_matches)
            return "Forgot the matching personal memory." if removed else "I do not have a matching active personal memory."

        correction = re.match(r"^(?:actually|correction:?)\s+(?:my\s+)?(?:preferred\s+)?name\s+is\s+(.+)$", raw, re.I)
        if correction:
            self.update_profile({"preferred_name": correction.group(1).strip(" .?!")}, source=MemorySource.USER_CORRECTION)
            return "Updated your preferred name."

        if re.search(r"\b(?:remember|don't forget|do not forget|save this)\b", value) or re.search(r"\bmy\s+(?:name|preferred name)\s+is\b", value):
            content = re.sub(r"^\s*(?:remember|don't forget|do not forget|save this)\s+(?:that\s+)?", "", raw, flags=re.I).strip()
            name_match = re.search(r"\bmy\s+(?:preferred\s+)?name\s+is\s+(.+)$", content, re.I)
            if name_match:
                self.update_profile({"preferred_name": name_match.group(1).strip(" .?!")})
                return "Remembered your preferred name."
            birthday = re.search(r"\bmy\s+(?:birthday|date of birth)\s+is\s+(\d{4}-\d{2}-\d{2})", content, re.I)
            if birthday:
                from datetime import date
                normalized = date.fromisoformat(birthday.group(1)).isoformat()
                self.update_profile({"date_of_birth": normalized})
                return "Remembered your date of birth."
            if re.search(r"\bmy\s+(?:birthday|date of birth)\b", content, re.I):
                return "What date should I store for your birthday? Please use YYYY-MM-DD."
            relation = re.match(r"(.+?)\s+is\s+my\s+(partner|girlfriend|boyfriend|friend|mentor|colleague|family|classmate|teacher)\.?$", content, re.I)
            if relation:
                if relation.group(1).strip().lower() in {"he", "she", "they", "them", "him", "her", "that person"}:
                    return "Which person do you mean? I won't guess an identity from an ambiguous pronoun."
                self.add_relationship(RelationshipCreate(name=relation.group(1).strip(), relationship_type=relation.group(2).lower()))
                return "Remembered that relationship."
            preference = re.search(r"my\s+(?:response\s+)?preference\s+is\s+(.+)$", content, re.I)
            if preference:
                self.update_profile({"communication_style": {"response_style": preference.group(1).strip(" .?!"), "source": MemorySource.USER_EXPLICIT.value}}, source=MemorySource.USER_EXPLICIT)
                return "Remembered your communication preference."
            project = re.search(r"(?:i am|i'm|i am currently)\s+working on\s+(.+)$", content, re.I)
            if project:
                self.add(PersonalMemoryCreate(memory_type=MemoryKind.PROJECT, category="PROJECT", key="current_project", value={"name": project.group(1).strip(" .?!"), "status": "ACTIVE"}))
                return "Remembered your current project."
            self.add(PersonalMemoryCreate(memory_type=MemoryKind.CONTEXTUAL, category="CONTEXT", key=content[:120], value=content))
            return "Remembered that."

        if re.search(r"\b(?:what do you remember about me|show my profile|what do you know about me)\b", value):
            summary = self.summary()
            lines = []
            for title, key in (("IDENTITY", "identity"), ("WORK / EDUCATION", "work_education"), ("PROJECTS", "projects"), ("GOALS", "goals"), ("IMPORTANT PEOPLE", "important_people"), ("IMPORTANT DATES", "important_dates"), ("PREFERENCES", "preferences"), ("ASTROLOGY", "astrology")):
                if summary[key]:
                    lines.append(title + ":")
                    lines.extend(f"- {item}" for item in (summary[key] if isinstance(summary[key], list) else [summary[key]]))
            return "\n".join(lines) or "I do not currently have personal context stored."
        if re.search(r"\b(?:what is|what's) my (?:name|preferred name)\b", value):
            name = self.get_profile()["profile"].preferred_name
            return name or "I do not currently have your name stored."
        who = re.search(r"^(?:who is|what is my relationship with)\s+(.+?)[?!.]*$", raw, re.I)
        if who:
            people = self.relationships(who.group(1).strip())
            return "\n".join(f"{item['name']}: {item['relationship_type']}" for item in people) or "I do not have that relationship stored."
        if re.search(r"\b(?:what are|what is) my (?:current )?(?:projects?|goals?|work|education)\b", value):
            items = self.retrieve(raw)
            return "\n".join(f"- {item['category']}.{item['key']}: {item['value']}" for item in items) or "I do not have matching personal context stored."
        return None

    def _audit(self, action: str, memory_id: int | None, category: str | None, key: str | None) -> None:
        conn = get_connection(); conn.execute("INSERT INTO memory_audit(action, memory_id, category, key, created_at) VALUES (?, ?, ?, ?, ?)", (action, memory_id, category, key, now())); conn.commit(); conn.close()
        topic = {
            "MEMORY_CREATED": "memory.created",
            "MEMORY_CORRECTED": "memory.corrected",
            "MEMORY_DELETED": "memory.deleted",
            "MEMORY_DELETED_ALL": "memory.deleted",
            "PROFILE_UPDATED": "memory.updated",
        }.get(action, "memory.updated")
        # Event payloads intentionally omit values, names, and keys.
        event_bus.emit(topic, memory_id=memory_id, category=category, action=action)

    @staticmethod
    def _decode(row: Any) -> dict[str, Any]:
        item = dict(row); item["value"] = json.loads(item["value"]); item["active"] = bool(item["active"]); return item

    @staticmethod
    def _relationship(row: Any) -> dict[str, Any]:
        item = dict(row); item["important_dates"] = json.loads(item["important_dates"]); item["preferences"] = json.loads(item["preferences"]); item["active"] = bool(item["active"]); return item


personal_memory_service = PersonalMemoryService()
