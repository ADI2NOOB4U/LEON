import asyncio

from backend.app.config.settings import settings
from backend.app.core.providers.openai_compatible import OllamaProvider
from backend.app.core.router import ModelRouter


def test_ollama_models_are_selected_by_role(monkeypatch):
    monkeypatch.setattr(settings, "ollama_general_model", "general-test")
    monkeypatch.setattr(settings, "ollama_coding_model", "coding-test")
    monkeypatch.setattr(settings, "ollama_embedding_model", "embedding-test")

    assert OllamaProvider("general").model == "general-test"
    assert OllamaProvider("coding").model == "coding-test"
    assert OllamaProvider("embedding").model == "embedding-test"


def test_router_defaults_to_general_and_routes_coding(monkeypatch):
    router = ModelRouter()
    router.provider_name = "ollama"
    captured = []

    class Provider:
        async def chat(self, messages):
            captured.append(self.model)
            return "ok"

    def provider_for_role(role):
        provider = Provider()
        provider.model = role
        return provider

    monkeypatch.setattr(router, "_provider_for_role", provider_for_role)

    assert asyncio.run(router.chat([{"role": "user", "content": "hello"}])) == "ok"
    assert asyncio.run(router.chat([{"role": "user", "content": "code"}], role="coding")) == "ok"
    assert captured == ["general", "coding"]


def test_router_embedding_uses_embedding_role(monkeypatch):
    router = ModelRouter()
    router.provider_name = "ollama"
    captured = []

    class Provider:
        async def embed(self, text):
            captured.append(text)
            return [1.0, 2.0]

    monkeypatch.setattr(router, "_provider_for_role", lambda role: Provider())

    assert asyncio.run(router.embed("remember this")) == [1.0, 2.0]
    assert captured == ["remember this"]


def test_mock_mode_preserves_role_agnostic_behavior():
    router = ModelRouter()

    assert asyncio.run(
        router.chat([{"role": "user", "content": "hello"}], role="coding")
    ) == "LEON Core is online. You said: hello"
    assert len(asyncio.run(router.embed("remember this"))) == 8
