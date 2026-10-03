from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "LEON"


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "online"


def test_chat():
    response = client.post(
        "/api/chat",
        json={"message": "Hello LEON"},
    )

    assert response.status_code == 200
    assert "LEON Core is online" in response.json()["assistant"]
