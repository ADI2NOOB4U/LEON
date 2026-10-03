from typing import Any

import httpx

from backend.app.config.settings import settings
from backend.app.core.providers.base import ModelProvider


class OpenAICompatibleProvider(ModelProvider):

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def chat(self, messages: list[dict[str, str]]) -> str:
        if not self.model:
            raise RuntimeError("No model configured for this provider.")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )

        response.raise_for_status()
        data: dict[str, Any] = response.json()

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Unexpected model response: {data}"
            ) from exc

    async def embed(self, text: str) -> list[float]:
        if not self.model:
            raise RuntimeError("No model configured for this provider.")
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                json={"model": self.model, "input": text},
            )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        try:
            embedding = data["data"][0]["embedding"]
            if not isinstance(embedding, list):
                raise TypeError
            return [float(value) for value in embedding]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Unexpected embedding response: {data}") from exc


class OllamaProvider(OpenAICompatibleProvider):
    def __init__(self, role: str = "general"):
        super().__init__(
            base_url=settings.ollama_base_url,
            model={
                "general": settings.ollama_general_model or settings.ollama_model,
                "coding": settings.ollama_coding_model,
                "embedding": settings.ollama_embedding_model,
            }.get(role, settings.ollama_general_model or settings.ollama_model),
        )


class ColibriProvider(OpenAICompatibleProvider):
    def __init__(self):
        super().__init__(
            base_url=settings.colibri_base_url,
            model=settings.colibri_model,
        )
