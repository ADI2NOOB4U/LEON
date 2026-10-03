import asyncio

from fastapi.testclient import TestClient

from backend.app.core.agent import LeonAgent
from backend.app.db.database import get_connection, init_db
from backend.app.memory.memory import memory_service
from backend.app.main import app


client = TestClient(app)


def setup_function():
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM memory")
    conn.commit()
    conn.close()


def test_memory_crud_and_search():
    response = client.post(
        "/api/memory",
        json={"type": "preference", "content": "Prefers concise answers", "importance": 0.8},
    )
    assert response.status_code == 201
    memory = response.json()
    assert memory["type"] == "preference"
    assert memory["importance"] == 0.8
    assert client.get("/api/memory").json() == [memory]
    assert client.get("/api/memory/search?q=CONCISE").json() == [memory]
    assert client.delete(f"/api/memory/{memory['id']}").status_code == 204
    assert client.get("/api/memory").json() == []


def test_memory_validates_type_content_and_importance():
    assert client.post("/api/memory", json={"type": "unknown", "content": "x"}).status_code == 422
    assert client.post("/api/memory", json={"type": "fact", "content": "   "}).status_code == 422
    assert client.post("/api/memory", json={"type": "fact", "content": "x", "importance": 2}).status_code == 422


def test_delete_missing_memory_returns_not_found():
    assert client.delete("/api/memory/999999").status_code == 404


def test_retrieve_relevant_memories_is_bounded_and_contains_type_and_content():
    memory_service.add("preference", "Favorite color is blue", importance=0.9)
    memory_service.add("project", "Unrelated migration details " + "x" * 200)

    memories = memory_service.retrieve_relevant(
        "What is my favorite color?", limit=5, max_chars=80
    )
    context = memory_service.context_for("What is my favorite color?", max_chars=80)

    assert memories == [{"type": "preference", "content": "Favorite color is blue"}]
    assert "preference" in context
    assert "Favorite color is blue" in context
    assert "migration" not in context
    assert len(context) <= 80


def test_agent_injects_only_relevant_memory_context():
    memory_service.add("preference", "Prefers concise answers")
    memory_service.add("fact", "Lives in an unrelated city")
    captured = {}

    class CapturingRouter:
        async def chat(self, messages):
            captured["messages"] = messages
            return "ok"

    agent = LeonAgent()
    agent.router = CapturingRouter()
    assert asyncio.run(agent.chat("Please give concise answers")) == "ok"

    system = captured["messages"][0]["content"]
    assert "preference: Prefers concise answers" in system
    assert "unrelated city" not in system
