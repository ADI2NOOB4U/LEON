import asyncio

from fastapi.testclient import TestClient

from backend.app.core.agent import LeonAgent
from backend.app.db.database import get_connection, init_db
from backend.app.main import app


client = TestClient(app)


def setup_function():
    init_db()
    conn = get_connection()
    conn.execute("UPDATE user_profile SET data = '{}', settings = '{}' WHERE id = 1")
    for table in ("personal_memories", "relationships", "important_dates", "memory_audit"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()


def test_explicit_identity_survives_and_can_be_forgotten():
    assert client.post("/api/command", json={"message": "Remember my name is Test User."}).json()["message"] == "Remembered your preferred name."
    assert client.get("/api/memory/profile").json()["profile"]["preferred_name"] == "Test User"
    assert client.post("/api/command", json={"message": "What is my name?"}).json()["message"] == "Test User"

    assert client.post("/api/command", json={"message": "Forget my name."}).json()["message"] == "Forgot your preferred name."
    assert client.get("/api/memory/profile").json()["profile"]["preferred_name"] is None
    assert "do not currently" in client.post("/api/command", json={"message": "What is my name?"}).json()["message"]


def test_relationship_correction_and_date_storage():
    stored = client.post("/api/command", json={"message": "Remember Alex is my partner."}).json()
    assert stored["verified"] is True
    assert client.get("/api/memory/relationships", params={"name": "Alex"}).json()[0]["relationship_type"] == "partner"

    date_response = client.post("/api/memory/important-dates", json={"name": "Alex birthday", "date_value": "2030-04-05", "date_type": "birthday"})
    assert date_response.status_code == 201
    assert date_response.json()["date_value"] == "2030-04-05"

    result = client.post("/api/command", json={"message": "Alex is no longer my partner."}).json()
    assert "no longer" in result["message"]
    assert client.get("/api/memory/relationships").json() == []

    reminder = client.post("/api/command", json={"message": "Remind me a week before."}).json()
    assert "Scheduled a reminder" in reminder["message"]


def test_correction_supersedes_active_memory_and_secret_is_rejected():
    created = client.post("/api/memory/personal", json={"memory_type": "PREFERENCE", "category": "PREFERENCE", "key": "response_style", "value": "concise"})
    assert created.status_code == 201
    corrected = client.post("/api/memory/correct", json={"memory_id": created.json()["id"], "value": "technical"})
    assert corrected.status_code == 200
    current = client.get("/api/memory/personal", params={"category": "PREFERENCE"}).json()
    assert len(current) == 1 and current[0]["value"] == "technical"
    assert client.post("/api/memory/personal", json={"memory_type": "CONTEXTUAL", "category": "CONTEXT", "key": "credential", "value": "api_key=do-not-store"}).status_code == 422


def test_summary_and_agent_use_the_same_persisted_memory_engine():
    client.post("/api/command", json={"message": "Remember I am working on the Atlas project."})
    summary = client.get("/api/memory/summary").json()
    assert any(item["key"] == "current_project" for item in summary["memories"])

    result = asyncio.run(LeonAgent().chat("What is my current project?"))
    assert "Atlas" in result
