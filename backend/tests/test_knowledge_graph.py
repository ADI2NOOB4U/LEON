"""
Tests for Personal Knowledge Graph and Memory subsystem.
"""
import pytest
from backend.app.memory.knowledge import KnowledgeGraphService
from backend.app.memory.models import (
    EntityType,
    FactType,
    KnowledgeEntityCreate,
    KnowledgeFactCreate,
    KnowledgeRelationCreate,
    RelationType,
)


def test_add_and_get_entity():
    service = KnowledgeGraphService()
    created = service.add_entity(
        KnowledgeEntityCreate(
            name="Aditya Test",
            entity_type=EntityType.PERSON,
            description="System Architect",
            metadata={"role": "engineer"},
        )
    )
    assert created.name == "Aditya Test"
    assert created.entity_type == EntityType.PERSON
    assert created.description == "System Architect"


def test_add_relation_and_fact():
    service = KnowledgeGraphService()
    service.add_entity(KnowledgeEntityCreate(name="LEON Architecture", entity_type=EntityType.CONCEPT))
    service.add_entity(KnowledgeEntityCreate(name="FastAPI", entity_type=EntityType.TECHNOLOGY))

    rel = service.add_relation(
        KnowledgeRelationCreate(
            source_name="LEON Architecture",
            target_name="FastAPI",
            relation_type=RelationType.DEPENDS_ON,
            confidence=0.98,
        )
    )
    assert rel.source_name == "LEON Architecture"
    assert rel.target_name == "FastAPI"

    fact = service.add_fact(
        KnowledgeFactCreate(
            entity_name="LEON Architecture",
            fact_type=FactType.SPECIFICATION,
            statement="Backend utilizes FastAPI with async event bus.",
            importance=0.85,
        )
    )
    assert fact.entity_name == "LEON Architecture"
    assert fact.fact_type == FactType.SPECIFICATION
    assert fact.stale is False

    summary = service.get_graph_summary()
    assert summary.total_entities >= 2
    assert summary.total_relations >= 1
    assert summary.total_facts >= 1


def test_query_knowledge_relevance():
    service = KnowledgeGraphService()
    service.add_entity(
        KnowledgeEntityCreate(
            name="Quantum Router Project",
            entity_type=EntityType.PROJECT,
            description="High-speed routing kernel",
        )
    )
    results = service.query_knowledge("What is the Quantum Router Project?")
    assert len(results["entities"]) >= 1
    assert any(e.name == "Quantum Router Project" for e in results["entities"])

    # Query irrelevant string
    irrelevant = service.query_knowledge("What time is it?")
    assert len(irrelevant["entities"]) == 0
    assert len(irrelevant["facts"]) == 0

