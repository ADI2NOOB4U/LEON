import asyncio

import pytest

from backend.app.config.settings import settings
from backend.app.core.agent import LeonAgent
from backend.app.core.providers.openai_compatible import OllamaProvider
from backend.app.core.router import ModelRouter, MockProvider


def test_ollama_models_are_selected_by_role(monkeypatch):
    monkeypatch.setattr(settings, "ollama_general_model", "general-test")
    monkeypatch.setattr(settings, "ollama_coding_model", "coding-test")
    monkeypatch.setattr(settings, "ollama_embedding_model", "embedding-test")

    assert OllamaProvider("general").model == "general-test"
    assert OllamaProvider("coding").model == "coding-test"
    assert OllamaProvider("embedding").model == "embedding-test"


def test_required_ollama_models_are_bound_to_their_roles(monkeypatch):
    monkeypatch.setattr(settings, "ollama_general_model", "qwen3:8b")
    monkeypatch.setattr(settings, "ollama_coding_model", "qwen2.5-coder:7b")
    monkeypatch.setattr(settings, "ollama_embedding_model", "qwen3-embedding:0.6b")
    monkeypatch.setattr(settings, "vision_model", "qwen3-vl:8b")

    assert OllamaProvider("general").model == "qwen3:8b"
    assert OllamaProvider("coding").model == "qwen2.5-coder:7b"
    assert OllamaProvider("embedding").model == "qwen3-embedding:0.6b"
    assert OllamaProvider("vision").model == "qwen3-vl:8b"


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
    router.provider_name = "mock"
    router.provider = MockProvider()

    assert asyncio.run(
        router.chat([{"role": "user", "content": "hello"}], role="coding")
    ) == "LEON Core is online. You said: hello"
    assert len(asyncio.run(router.embed("remember this"))) == 8


@pytest.mark.parametrize(
    ("prompt", "expected_role", "expected_model"),
    [
        ("Explain how photosynthesis works.", "general", "qwen3:8b"),
        ("Write code to parse CSV files.", "coding", "qwen2.5-coder:7b"),
        ("Describe this image.", "vision", "qwen3-vl:8b"),
    ],
)
def test_automatic_routes_select_the_expected_ollama_model(
    monkeypatch, prompt, expected_role, expected_model
):
    monkeypatch.setattr(settings, "ollama_general_model", "qwen3:8b")
    monkeypatch.setattr(settings, "ollama_coding_model", "qwen2.5-coder:7b")
    monkeypatch.setattr(settings, "vision_model", "qwen3-vl:8b")

    role = ModelRouter.route_for_text(prompt)

    assert role == expected_role
    assert OllamaProvider(role).model == expected_model


@pytest.mark.parametrize(
    "prompt",
    [
        "What is the current status?",
        "Tell me the latest release.",
        "What happened today?",
    ],
)
def test_current_world_requests_route_to_live_research(prompt):
    assert ModelRouter.route_for_text(prompt) == "research"


def test_explicit_gemini_request_routes_to_gemini():
    assert ModelRouter.route_for_text("Use Gemini to explain photosynthesis.") == "gemini"


def test_explicit_gemini_request_calls_gemini(monkeypatch):
    monkeypatch.setattr(settings, "cloud_ai_enabled", True)
    router = ModelRouter()
    calls = []

    class FakeGeminiProvider:
        async def chat(self, messages, **kwargs):
            calls.append((messages, kwargs))
            return "Gemini answer"

    monkeypatch.setattr("backend.app.core.router.GeminiProvider", FakeGeminiProvider)
    prompt = "Use Gemini to explain photosynthesis."

    assert asyncio.run(
        router.chat(
            [{"role": "user", "content": prompt}],
            role=ModelRouter.route_for_text(prompt),
            allow_cloud=True,
        )
    ) == "Gemini answer"
    assert calls == [([{"role": "user", "content": prompt}], {"grounding": False})]


def test_safe_public_request_uses_gemini_after_ollama_failure(monkeypatch):
    monkeypatch.setattr(settings, "cloud_ai_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", type(settings.gemini_api_key)("test-key"))
    router = ModelRouter()
    router.provider_name = "ollama"
    messages = [
        {"role": "system", "content": "private memory must stay local"},
        {"role": "user", "content": "What is photosynthesis?"},
    ]
    calls = []

    class FailingLocalProvider:
        async def chat(self, _messages):
            raise RuntimeError("Ollama is unavailable")

    class FakeGeminiProvider:
        async def chat(self, cloud_messages, **kwargs):
            calls.append((cloud_messages, kwargs))
            return "A plant process."

    monkeypatch.setattr(router, "_provider_for_role", lambda _role: FailingLocalProvider())
    monkeypatch.setattr("backend.app.core.router.GeminiProvider", FakeGeminiProvider)

    response = asyncio.run(router.chat(messages, allow_cloud=True))

    assert response == "A plant process."
    assert calls == [([{"role": "user", "content": "What is photosynthesis?"}], {"grounding": False})]


def test_private_request_never_falls_back_to_cloud(monkeypatch):
    monkeypatch.setattr(settings, "cloud_ai_enabled", True)
    router = ModelRouter()
    router.provider_name = "ollama"
    cloud_calls = []

    class FailingLocalProvider:
        async def chat(self, _messages):
            raise RuntimeError("Ollama is unavailable")

    class FakeGeminiProvider:
        async def chat(self, *args, **kwargs):
            cloud_calls.append((args, kwargs))
            return "must not be called"

    monkeypatch.setattr(router, "_provider_for_role", lambda _role: FailingLocalProvider())
    monkeypatch.setattr("backend.app.core.router.GeminiProvider", FakeGeminiProvider)

    with pytest.raises(RuntimeError, match="Ollama is unavailable"):
        asyncio.run(
            router.chat(
                [{"role": "user", "content": "Summarize my private medical file."}],
                allow_cloud=True,
            )
        )
    assert not cloud_calls


def test_current_world_route_calls_gemini_with_search_grounding(monkeypatch):
    monkeypatch.setattr(settings, "cloud_ai_enabled", True)
    monkeypatch.setattr(settings, "cloud_ai_search_grounding", True)
    router = ModelRouter()
    calls = []

    class FakeGeminiProvider:
        async def chat(self, messages, **kwargs):
            calls.append((messages, kwargs))
            return "Latest answer"

    monkeypatch.setattr("backend.app.core.router.GeminiProvider", FakeGeminiProvider)

    response = asyncio.run(
        router.chat(
            [{"role": "user", "content": "What is the latest AI news today?"}],
            allow_cloud=True,
        )
    )

    assert response == "Latest answer"
    assert calls == [
        (
            [{"role": "user", "content": "What is the latest AI news today?"}],
            {"grounding": True},
        )
    ]


def test_current_world_route_fails_if_search_grounding_is_disabled(monkeypatch):
    monkeypatch.setattr(settings, "cloud_ai_enabled", True)
    monkeypatch.setattr(settings, "cloud_ai_search_grounding", False)
    router = ModelRouter()

    with pytest.raises(RuntimeError, match="requires Google Search grounding"):
        asyncio.run(
            router.chat(
                [{"role": "user", "content": "What happened today?"}],
                allow_cloud=True,
            )
        )


def test_image_input_uses_vision_role_only(monkeypatch):
    router = ModelRouter()
    router.provider_name = "ollama"
    calls = []

    class Provider:
        model = "qwen3-vl:8b"

        async def vision_chat(self, prompt, image, mime_type):
            calls.append((self.model, image, mime_type))
            return "<think>inspect pixels</think>Final image answer"

    monkeypatch.setattr(router, "_create_provider", lambda role="general": Provider())

    assert asyncio.run(router.vision_chat("Describe it", b"image", "image/png")) == "Final image answer"
    assert calls == [("qwen3-vl:8b", b"image", "image/png")]


def test_normal_agent_chat_never_invokes_vision_and_hides_reasoning():
    class Router:
        def __init__(self):
            self.roles = []
            self.vision_calls = 0

        async def chat(self, messages, role="general"):
            self.roles.append(role)
            return "<think>private reasoning</think>Visible answer"

        async def vision_chat(self, *args):
            self.vision_calls += 1
            raise AssertionError("vision must not be used for text chat")

    router = Router()
    agent = LeonAgent()
    agent.router = router

    assert asyncio.run(agent.chat("Hello LEON")) == "Visible answer"
    assert router.roles == ["general"]
    assert router.vision_calls == 0
