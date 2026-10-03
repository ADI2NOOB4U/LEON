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
        self.provider_name = settings.model_provider.lower()
        self.provider = self._create_provider()

    def _create_provider(self) -> ModelProvider:

        if self.provider_name == "ollama":
            return OllamaProvider()

        if self.provider_name == "colibri":
            return ColibriProvider()

        if self.provider_name == "mock":
            return MockProvider()

        raise ValueError(
            f"Unsupported model provider: {self.provider_name}"
        )

    async def chat(self, messages: list[dict[str, str]]) -> str:
        return await self.provider.chat(messages)
