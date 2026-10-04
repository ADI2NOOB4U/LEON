from fastapi.testclient import TestClient

from backend.app.db.database import get_connection, init_db
from backend.app.main import app


client = TestClient(app)


def setup_function():
    init_db()
    conn = get_connection()
    for table in ("improvement_feedback", "improvement_proposals", "improvement_profile"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit(); conn.close()


def test_feedback_creates_gated_self_improvement_profile():
    for _ in range(2):
        response = client.post("/api/improvement/feedback", json={
            "request": "Summarize this report",
            "outcome": "Too vague",
            "rating": 2,
            "route": "chat.general",
        })
        assert response.status_code == 200

    learned = client.post("/api/improvement/learn")
    assert learned.status_code == 200
    assert learned.json()["status"] == "activated"
    profile = client.get("/api/improvement/profile").json()
    assert "response_guidance" in profile["profile"]
    assert "permissions" not in profile["profile"]

    proposals = client.get("/api/improvement/proposals").json()
    assert proposals[0]["status"] == "active"
    rollback = client.post(f"/api/improvement/proposals/{proposals[0]['id']}/rollback")
    assert rollback.status_code == 200
    assert "response_guidance" not in rollback.json()["profile"]


def test_learning_does_not_change_without_repeated_negative_evidence():
    response = client.post("/api/improvement/learn")
    assert response.status_code == 200
    assert response.json()["status"] == "no_change"
