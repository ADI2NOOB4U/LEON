from backend.app.config.settings import settings
from backend.app.core.providers.base import ModelProvider
from backend.app.core.providers.openai_compatible import (
    ColibriProvider,
    OllamaProvider,
)

MODEL_ROLES = {"general", "coding", "embedding"}


class MockProvider(ModelProvider):

    async def chat(self, messages: list[dict[str, str]]) -> str:
        user_message = messages[-1]["content"]
        return f"LEON Core is online. You said: {user_message}"

    async def embed(self, text: str) -> list[float]:
        return [float((sum(text.encode()) + index) % 997) / 997 for index in range(8)]


class ModelRouter:

    def __init__(self):
        self.provider_name = self._normalize_provider_name(settings.model_provider)
        self.provider = self._create_provider()

    @staticmethod
    def _normalize_provider_name(name: str | None) -> str:
        value = (name or "mock").strip().lower()
        return value if value in {"mock", "ollama", "colibri"} else "mock"

    def _create_provider(self, role: str = "general") -> ModelProvider:
        try:
            if self.provider_name == "ollama":
                return OllamaProvider(role=role)

            if self.provider_name == "colibri":
                return ColibriProvider()

            return MockProvider()
        except Exception:
            self.provider_name = "mock"
            return MockProvider()

    @staticmethod
    def _normalize_role(role: str | None) -> str:
        value = (role or "general").strip().lower()
        if value not in MODEL_ROLES:
            raise ValueError(f"Unsupported model role: {value}")
        return value

    def _provider_for_role(self, role: str) -> ModelProvider:
        if role == "general" or self.provider_name == "mock":
            return self.provider
        return self._create_provider(role)

    async def chat(self, messages: list[dict[str, str]], role: str = "general") -> str:
        role = self._normalize_role(role)
        provider = self._provider_for_role(role)
        try:
            return await provider.chat(messages)
        except Exception:
            if self.provider_name != "mock":
                self.provider_name = "mock"
                self.provider = MockProvider()
                return await self.provider.chat(messages)
            raise

    async def embed(self, text: str, role: str = "embedding") -> list[float]:
        role = self._normalize_role(role)
        if role != "embedding":
            raise ValueError("Embedding calls must use the embedding role")
        provider = self._provider_for_role(role)
        try:
            return await provider.embed(text)
        except Exception:
            if self.provider_name != "mock":
                self.provider_name = "mock"
                self.provider = MockProvider()
                return await self.provider.embed(text)
            raise
