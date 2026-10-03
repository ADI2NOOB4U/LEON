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


def test_router_falls_back_to_mock_when_provider_is_unavailable():
    import asyncio

    from backend.app.core.router import ModelRouter

    router = ModelRouter()
    router.provider_name = "ollama"

    class FailingProvider:
        async def chat(self, messages):
            raise RuntimeError("provider unavailable")

    router.provider = FailingProvider()

    result = asyncio.run(router.chat([{"role": "user", "content": "Hello LEON"}]))

    assert "You said: Hello LEON" in result
