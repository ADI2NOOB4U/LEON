from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.db.database import get_connection, init_db, now
from backend.app.memory.models import (
    EntityType,
    FactType,
    KnowledgeEntity,
    KnowledgeEntityCreate,
    KnowledgeFact,
    KnowledgeFactCreate,
    KnowledgeGraphSummary,
    KnowledgeRelation,
    KnowledgeRelationCreate,
    RelationType,
)

_IRRELEVANT_PATTERNS = [
    re.compile(r"^(?:what\s+(?:is\s+the\s+)?time|what\s+time\s+is\s+it|current\s+time|date\s+today|today's\s+date|what\s+day\s+is\s+it)\b", re.IGNORECASE),
    re.compile(r"^(?:hi|hello|hey|greetings|howdy)(?:\s+leon)?$", re.IGNORECASE),
    re.compile(r"^(?:system\s+stats|cpu\s+usage|memory\s+usage|disk\s+usage)$", re.IGNORECASE),
]

_RELEVANT_PATTERNS = [
    re.compile(r"\b(?:project|project\s+name|what\s+is|what\s+did\s+i\s+call|remember|who\s+am\s+i|my\s+name|architecture|tech\s+stack|what\s+models|preference|configuration)\b", re.IGNORECASE),
    re.compile(r"\b(?:what\s+did\s+we\s+decide|yesterday|past\s+task|history|knowledge|graph|entity|fact)\b", re.IGNORECASE),
]


class KnowledgeGraphService:
    """Manages the Personal Knowledge Graph (Entities, Relations, and Facts)."""

    def __init__(self, db_path: str | None = None):
        if db_path is not None:
            from backend.app.db.database import set_db_path
            set_db_path(db_path)
        init_db()
        self._ensure_default_seed()

    def _ensure_default_seed(self) -> None:
        """Seed foundational system knowledge if database is fresh."""
        try:
            conn = get_connection()
            count = conn.execute("SELECT COUNT(*) as c FROM knowledge_entities").fetchone()["c"]
            conn.close()
            if count == 0:
                self.add_entity(KnowledgeEntityCreate(name="LEON", entity_type=EntityType.SYSTEM, description="Personal AI Operating System"))
                self.add_entity(KnowledgeEntityCreate(name="qwen3:8b", entity_type=EntityType.TECHNOLOGY, description="General local reasoning model"))
                self.add_entity(KnowledgeEntityCreate(name="qwen3-vl:8b", entity_type=EntityType.TECHNOLOGY, description="Vision perception model"))
                self.add_entity(KnowledgeEntityCreate(name="Intelligence Core", entity_type=EntityType.CONCEPT, description="Deterministic capability & model routing engine"))
                self.add_entity(KnowledgeEntityCreate(name="Computer Use", entity_type=EntityType.CONCEPT, description="Observe-Act-Verify desktop automation"))
                
                self.add_relation(KnowledgeRelationCreate(source_name="LEON", target_name="qwen3:8b", relation_type=RelationType.USES))
                self.add_relation(KnowledgeRelationCreate(source_name="LEON", target_name="qwen3-vl:8b", relation_type=RelationType.USES))
                self.add_relation(KnowledgeRelationCreate(source_name="LEON", target_name="Intelligence Core", relation_type=RelationType.CONTAINS))
                self.add_relation(KnowledgeRelationCreate(source_name="LEON", target_name="Computer Use", relation_type=RelationType.CONTAINS))

                self.add_fact(KnowledgeFactCreate(entity_name="LEON", fact_type=FactType.SPECIFICATION, statement="LEON is a local-first multimodal personal AI operating system.", importance=0.9))
        except Exception:
            pass

    def add_entity(self, entity: KnowledgeEntityCreate) -> KnowledgeEntity:
        conn = get_connection()
        ts = now()
        meta_json = json.dumps(entity.metadata or {})
        conn.execute(
            """
            INSERT INTO knowledge_entities(name, entity_type, description, confidence, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name, entity_type) DO UPDATE SET
                description = excluded.description,
                confidence = excluded.confidence,
                metadata = excluded.metadata,
                updated_at = excluded.updated_at
            """,
            (entity.name, entity.entity_type.value, entity.description, entity.confidence, meta_json, ts, ts),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM knowledge_entities WHERE name = ? AND entity_type = ?", (entity.name, entity.entity_type.value)).fetchone()
        conn.close()
        return self._row_to_entity(dict(row))

    def add_relation(self, relation: KnowledgeRelationCreate) -> KnowledgeRelation:
        conn = get_connection()
        ts = now()
        conn.execute(
            """
            INSERT INTO knowledge_relations(source_name, target_name, relation_type, confidence, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_name, target_name, relation_type) DO UPDATE SET
                confidence = excluded.confidence
            """,
            (relation.source_name, relation.target_name, relation.relation_type.value, relation.confidence, ts),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM knowledge_relations WHERE source_name = ? AND target_name = ? AND relation_type = ?",
            (relation.source_name, relation.target_name, relation.relation_type.value)
        ).fetchone()
        conn.close()
        return self._row_to_relation(dict(row))

    def add_fact(self, fact: KnowledgeFactCreate) -> KnowledgeFact:
        conn = get_connection()
        ts = now()
        cursor = conn.execute(
            """
            INSERT INTO knowledge_facts(entity_name, fact_type, statement, confidence, source, importance, last_verified, stale, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (fact.entity_name, fact.fact_type.value, fact.statement, fact.confidence, fact.source, fact.importance, ts, ts, ts),
        )
        fact_id = int(cursor.lastrowid)
        conn.commit()
        row = conn.execute("SELECT * FROM knowledge_facts WHERE id = ?", (fact_id,)).fetchone()
        conn.close()
        return self._row_to_fact(dict(row))

    def mark_fact_stale(self, fact_id: int) -> bool:
        conn = get_connection()
        ts = now()
        cursor = conn.execute("UPDATE knowledge_facts SET stale = 1, updated_at = ? WHERE id = ?", (ts, fact_id))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    def list_entities(self) -> List[KnowledgeEntity]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM knowledge_entities ORDER BY name ASC").fetchall()
        conn.close()
        return [self._row_to_entity(dict(r)) for r in rows]

    def list_relations(self) -> List[KnowledgeRelation]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM knowledge_relations ORDER BY id ASC").fetchall()
        conn.close()
        return [self._row_to_relation(dict(r)) for r in rows]

    def list_facts(self, include_stale: bool = False) -> List[KnowledgeFact]:
        conn = get_connection()
        query = "SELECT * FROM knowledge_facts" if include_stale else "SELECT * FROM knowledge_facts WHERE stale = 0"
        rows = conn.execute(query + " ORDER BY importance DESC, id DESC").fetchall()
        conn.close()
        return [self._row_to_fact(dict(r)) for r in rows]

    def get_graph_summary(self) -> KnowledgeGraphSummary:
        conn = get_connection()
        e_count = conn.execute("SELECT COUNT(*) as c FROM knowledge_entities").fetchone()["c"]
        r_count = conn.execute("SELECT COUNT(*) as c FROM knowledge_relations").fetchone()["c"]
        f_count = conn.execute("SELECT COUNT(*) as c FROM knowledge_facts WHERE stale = 0").fetchone()["c"]
        types_rows = conn.execute("SELECT entity_type, COUNT(*) as c FROM knowledge_entities GROUP BY entity_type").fetchall()
        conn.close()
        return KnowledgeGraphSummary(
            total_entities=e_count,
            total_relations=r_count,
            total_facts=f_count,
            entity_types={r["entity_type"]: r["c"] for r in types_rows},
        )

    def should_retrieve_memory(self, query: str) -> bool:
        """Heuristic check to avoid polluting zero-knowledge turns."""
        for pat in _IRRELEVANT_PATTERNS:
            if pat.search(query):
                return False
        for pat in _RELEVANT_PATTERNS:
            if pat.search(query):
                return True
        return False

    def query_knowledge(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Retrieve relevant knowledge entities and facts for a prompt."""
        if not self.should_retrieve_memory(query):
            return {"entities": [], "relations": [], "facts": []}

        tokens = set(re.findall(r"\w+", query.lower()))
        entities = self.list_entities()
        matched_entities = []
        for e in entities:
            e_tokens = set(re.findall(r"\w+", e.name.lower()))
            if tokens.intersection(e_tokens):
                matched_entities.append(e)

        facts = self.list_facts(include_stale=False)
        matched_facts = []
        for f in facts:
            f_tokens = set(re.findall(r"\w+", f.statement.lower()))
            if tokens.intersection(f_tokens) or any(e.name == f.entity_name for e in matched_entities):
                matched_facts.append(f)

        return {
            "entities": matched_entities[:limit],
            "facts": matched_facts[:limit],
        }

    @staticmethod
    def _row_to_entity(row: dict) -> KnowledgeEntity:
        return KnowledgeEntity(
            id=row["id"],
            name=row["name"],
            entity_type=EntityType(row["entity_type"]),
            description=row.get("description"),
            confidence=row.get("confidence", 1.0),
            metadata=json.loads(row["metadata"]) if row.get("metadata") else {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_relation(row: dict) -> KnowledgeRelation:
        return KnowledgeRelation(
            id=row["id"],
            source_name=row["source_name"],
            target_name=row["target_name"],
            relation_type=RelationType(row["relation_type"]),
            confidence=row.get("confidence", 1.0),
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_fact(row: dict) -> KnowledgeFact:
        return KnowledgeFact(
            id=row["id"],
            entity_name=row["entity_name"],
            fact_type=FactType(row["fact_type"]),
            statement=row["statement"],
            confidence=row.get("confidence", 1.0),
            source=row.get("source", "user"),
            importance=row.get("importance", 0.5),
            last_verified=row.get("last_verified"),
            stale=bool(row.get("stale", 0)),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


knowledge_service = KnowledgeGraphService()
