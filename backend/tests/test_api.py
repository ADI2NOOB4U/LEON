import pytest
from fastapi.testclient import TestClient

from backend.app.config.settings import Settings, settings
from backend.app.main import app


client = TestClient(app)


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
)
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_frontend_cors_preflight(origin, method):
    response = client.options(
        "/api/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert method in response.headers["access-control-allow-methods"]
    assert "access-control-allow-credentials" not in response.headers


def test_development_cors_origins_are_not_added_in_production():
    production_settings = Settings(_env_file=None, app_env="production")

    assert production_settings.cors_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "LEON"


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "online"


def test_chat(monkeypatch):
    from backend.app.api.chat import agent
    from backend.app.core.router import MockProvider

    monkeypatch.setattr(agent.router, "provider_name", "mock")
    monkeypatch.setattr(agent.router, "provider", MockProvider())
    response = client.post(
        "/api/chat",
        json={"message": "Hello LEON"},
    )

    assert response.status_code == 200
    assert "LEON Core is online" in response.json()["assistant"]


def test_command_chat_returns_model_response(monkeypatch):
    from backend.app.api.chat import agent
    from backend.app.api.command import interpreter
    from backend.app.core.interpreter import CommandIntent

    async def reply(message):
        return f"Local response to: {message}"

    async def classify(_message):
        return CommandIntent(intent="chat", title="")

    monkeypatch.setattr(agent, "chat", reply)
    monkeypatch.setattr(interpreter, "interpret", classify)
    response = client.post("/api/command", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json()["type"] == "chat"
    assert response.json()["message"] == "Local response to: hello"


def test_openai_compatible_provider_returns_content(monkeypatch):
    import asyncio
    import httpx

    from backend.app.core.providers.openai_compatible import OpenAICompatibleProvider

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


def test_router_does_not_hide_provider_failure_as_mock(monkeypatch):
    import asyncio

    from backend.app.config.settings import settings
    from backend.app.core.router import ModelRouter

    router = ModelRouter()
    router.provider_name = "ollama"
    monkeypatch.setattr(settings, "cloud_ai_enabled", False)

    class FailingProvider:
        async def chat(self, messages):
            raise RuntimeError("provider unavailable")

    router.provider = FailingProvider()

    with pytest.raises(RuntimeError, match="provider unavailable"):
        asyncio.run(router.chat([{"role": "user", "content": "Hello LEON"}]))


def test_chat_provider_error_response_never_echoes_exception(monkeypatch):
    from backend.app.api.chat import agent

    class LeakingProvider:
        async def chat(self, messages):
            raise RuntimeError("GEMINI_API_KEY=must-not-be-returned")

    monkeypatch.setattr(agent.router, "provider_name", "ollama")
    monkeypatch.setattr(agent.router, "provider", LeakingProvider())
    monkeypatch.setattr(settings, "cloud_ai_enabled", False)

    response = client.post("/api/chat", json={"message": "Hello LEON"})

    assert response.status_code == 502
    assert "must-not-be-returned" not in response.text
    assert "GEMINI_API_KEY" not in response.text
