import base64
from typing import Any

import httpx

from backend.app.config.settings import settings
from backend.app.core.providers.base import ModelProvider
from backend.app.security.cloud_privacy import CloudPrivacyError, public_cloud_input


class OpenAICompatibleProvider(ModelProvider):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        if not self.model:
            raise RuntimeError("No model configured for this provider.")
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    **kwargs,
                },
            )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected model response: {data}") from exc

    async def vision_chat(self, prompt: str, image: bytes, mime_type: str) -> str:
        if not self.model:
            raise RuntimeError("No vision model configured for this provider.")
        encoded = base64.b64encode(image).decode("ascii")
        payload = {"model": self.model, "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
        ]}], "temperature": 0.2}
        async with httpx.AsyncClient(timeout=settings.vision_timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise TypeError
            return content.strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected vision model response: {data}") from exc

    async def embed(self, text: str) -> list[float]:
        if not self.model:
            raise RuntimeError("No model configured for this provider.")
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(f"{self.base_url}/embeddings", json={"model": self.model, "input": text})
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        try:
            embedding = data["data"][0]["embedding"]
            if not isinstance(embedding, list):
                raise TypeError
            return [float(value) for value in embedding]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Unexpected embedding response: {data}") from exc


class GeminiProvider(ModelProvider):
    def __init__(self, model: str | None = None):
        self.model = model or settings.cloud_ai_model
        self.base_url = settings.gemini_base_url.rstrip("/").removesuffix("/models")

    def _request_headers(self) -> dict[str, str]:
        api_key = settings.gemini_api_key.get_secret_value().strip() if settings.gemini_api_key else ""
        return {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    def _payload(self, user_input: str, *, grounding: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "input": user_input,
            "store": False,
        }
        if grounding and settings.cloud_ai_search_grounding:
            payload["tools"] = [{"type": "google_search"}]
        return payload

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        if not settings.gemini_api_key.get_secret_value().strip():
            raise RuntimeError("Gemini API key is not configured.")
        try:
            user_input = public_cloud_input(messages)
        except CloudPrivacyError:
            raise
        payload = self._payload(user_input, grounding=bool(kwargs.get("grounding")))
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            url = f"{self.base_url}/interactions"
        response = await client.post(url, headers=self._request_headers(), json=payload)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Gemini returned a malformed interaction response.")
        answer = self._interaction_text(data)
        api_key = settings.gemini_api_key.get_secret_value().strip()
        return answer.replace(api_key, "[REDACTED]") if api_key else answer

    @staticmethod
    def _interaction_text(data: dict[str, Any]) -> str:
        steps = data.get("steps")
        if not isinstance(steps, list):
            raise RuntimeError("Gemini returned a malformed interaction response.")

        output_blocks = []
        for step in steps:
            if not isinstance(step, dict) or step.get("type") != "model_output":
                continue
            content = step.get("content")
            if not isinstance(content, list):
                continue
            output_blocks.extend(
                block
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        text = "\n".join(
            block["text"].strip()
            for block in output_blocks
            if isinstance(block.get("text"), str) and block["text"].strip()
        )
        if not text:
            raise RuntimeError("Gemini returned no text content.")

        citations: list[str] = []
        seen_urls: set[str] = set()
        for block in output_blocks:
            annotations = block.get("annotations", [])
            if not isinstance(annotations, list):
                continue
            for annotation in annotations:
                if (
                    not isinstance(annotation, dict)
                    or annotation.get("type") != "url_citation"
                ):
                    continue
                url = annotation.get("url")
                if not isinstance(url, str) or url in seen_urls:
                    continue
                seen_urls.add(url)
                title = annotation.get("title")
                citations.append(f"- {title if isinstance(title, str) and title else url}: {url}")
        return text + (("\n\nSources:\n" + "\n".join(citations)) if citations else "")

    async def embed(self, text: str) -> list[float]:
        if not settings.gemini_api_key.get_secret_value().strip():
            raise RuntimeError("Gemini API key is not configured.")
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(
                f"{self.base_url}/models/{settings.cloud_ai_embedding_model}:embedContent",
                headers=self._request_headers(),
                json={
                    "content": {"parts": [{"text": text}]},
                },
            )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        try:
            embedding = data["embedding"]["values"]
            if not isinstance(embedding, list):
                raise TypeError
            return [float(value) for value in embedding]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("Unexpected Gemini embedding response.") from exc


class OllamaProvider(OpenAICompatibleProvider):
    def __init__(self, role: str = "general"):
        super().__init__(settings.ollama_base_url, {
            "general": settings.ollama_general_model or settings.ollama_model,
            "coding": settings.ollama_coding_model,
            "embedding": settings.ollama_embedding_model,
            "vision": settings.vision_model,
        }.get(role, settings.ollama_general_model or settings.ollama_model))


class ColibriProvider(OpenAICompatibleProvider):
    def __init__(self):
        super().__init__(settings.colibri_base_url, settings.colibri_model)
