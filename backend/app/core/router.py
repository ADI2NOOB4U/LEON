from backend.app.config.settings import settings
from backend.app.core.providers.base import ModelProvider
from backend.app.core.providers.openai_compatible import (
    ColibriProvider,
    OllamaProvider,
)


class MockProvider(ModelProvider):

    async def chat(self, messages: list[dict[str, str]]) -> str:
        user_message = messages[-1]["content"]
        return f"LEON Core is online. You said: {user_message}"


class ModelRouter:

    def __init__(self):
        self.provider_name = self._normalize_provider_name(settings.model_provider)
        self.provider = self._create_provider()

    @staticmethod
    def _normalize_provider_name(name: str | None) -> str:
        value = (name or "mock").strip().lower()
        return value if value in {"mock", "ollama", "colibri"} else "mock"

    def _create_provider(self) -> ModelProvider:
        try:
            if self.provider_name == "ollama":
                return OllamaProvider()

            if self.provider_name == "colibri":
                return ColibriProvider()

            return MockProvider()
        except Exception:
            self.provider_name = "mock"
            return MockProvider()

    async def chat(self, messages: list[dict[str, str]]) -> str:
        try:
            return await self.provider.chat(messages)
        except Exception:
            if self.provider_name != "mock":
                self.provider_name = "mock"
                self.provider = MockProvider()
                return await self.provider.chat(messages)
            raise
