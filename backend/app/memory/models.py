from __future__ import annotations

from enum import StrEnum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EntityType(StrEnum):
    PERSON = "person"
    PROJECT = "project"
    PREFERENCE = "preference"
    SYSTEM = "system"
    TECHNOLOGY = "technology"
    CONCEPT = "concept"
    WORKFLOW = "workflow"


class RelationType(StrEnum):
    USES = "uses"
    DEPENDS_ON = "depends_on"
    MANAGES = "manages"
    AUTHORED_BY = "authored_by"
    ASSISTS = "assists"
    CONTAINS = "contains"
    CONFIGURED_FOR = "configured_for"
    RELATES_TO = "relates_to"


class FactType(StrEnum):
    SPECIFICATION = "specification"
    PREFERENCE = "preference"
    OBSERVATION = "observation"
    CONFIGURATION = "configuration"
    STATE = "state"
    HISTORY = "history"


class KnowledgeEntityCreate(BaseModel):
    name: str
    entity_type: EntityType = EntityType.CONCEPT
    description: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeEntity(BaseModel):
    id: int
    name: str
    entity_type: EntityType
    description: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class KnowledgeRelationCreate(BaseModel):
    source_name: str
    target_name: str
    relation_type: RelationType = RelationType.RELATES_TO
    confidence: float = 1.0


class KnowledgeRelation(BaseModel):
    id: int
    source_name: str
    target_name: str
    relation_type: RelationType
    confidence: float = 1.0
    created_at: str


class KnowledgeFactCreate(BaseModel):
    entity_name: str
    fact_type: FactType = FactType.SPECIFICATION
    statement: str
    confidence: float = 1.0
    source: str = "user"
    importance: float = 0.5


class KnowledgeFact(BaseModel):
    id: int
    entity_name: str
    fact_type: FactType
    statement: str
    confidence: float = 1.0
    source: str = "user"
    importance: float = 0.5
    last_verified: Optional[str] = None
    stale: bool = False
    created_at: str
    updated_at: str


class KnowledgeGraphSummary(BaseModel):
    total_entities: int
    total_relations: int
    total_facts: int
    entity_types: Dict[str, int] = Field(default_factory=dict)

