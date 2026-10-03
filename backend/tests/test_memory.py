from fastapi.testclient import TestClient

from backend.app.db.database import get_connection, init_db
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
