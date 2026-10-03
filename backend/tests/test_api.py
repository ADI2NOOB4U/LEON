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


def test_openai_compatible_provider_returns_content(monkeypatch):
    import asyncio
    import importlib
    import httpx

    module = importlib.import_module("backend.app.core.providers.openai_compatible")
    assert module.Any is not None

    OpenAICompatibleProvider = module.OpenAICompatibleProvider

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "hello from provider"}}]}

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        async def post(self, *args, **kwargs):
            return DummyResponse()

    monkeypatch.setattr(httpx, "AsyncClient", DummyAsyncClient)
    provider = OpenAICompatibleProvider("http://example.com/v1", "demo-model")

    result = asyncio.run(provider.chat([{"role": "user", "content": "Hello"}]))

    assert result == "hello from provider"


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
