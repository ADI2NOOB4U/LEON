import re

from backend.app.config.settings import settings
from backend.app.core.providers.base import ModelProvider
from backend.app.core.providers.openai_compatible import ColibriProvider, GeminiProvider, OllamaProvider
from backend.app.security.cloud_privacy import (
    CloudPrivacyError,
    is_safe_public_cloud_text,
    public_cloud_input,
)


MODEL_ROLES = {"general", "coding", "embedding", "vision", "research", "gemini"}
_CURRENT_WORLD_KEYWORDS = {
    "today", "now", "current", "latest", "recent", "this morning", "this evening",
    "this week", "breaking", "current status", "current price", "current version",
    "what happened", "what changed", "current affairs", "news", "geopolitics",
    "war", "conflict", "cybersecurity incident", "latest release", "current schedule",
}

_REASONING_BLOCK = re.compile(
    r"(?:<think>|<thinking>|<reasoning>|<analysis>|<\|thinking\|>|<\|analysis\|>)"
    r".*?"
    r"(?:</think>|</thinking>|</reasoning>|</analysis>|<\|/thinking\|>|<\|/analysis\|>)",
    re.IGNORECASE | re.DOTALL,
)
_UNCLOSED_REASONING = re.compile(
    r"(?:<think>|<thinking>|<reasoning>|<analysis>|<\|thinking\|>|<\|analysis\|>).*$",
    re.IGNORECASE | re.DOTALL,
)


def final_model_response(content: str) -> str:
    """Return only user-facing content, excluding model reasoning markers."""
    if not isinstance(content, str):
        return ""
    content = _REASONING_BLOCK.sub("", content)
    content = _UNCLOSED_REASONING.sub("", content)
    return content.strip()


class MockProvider(ModelProvider):
    async def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        return f"LEON Core is online. You said: {messages[-1]['content']}"

    async def embed(self, text: str) -> list[float]:
        return [float((sum(text.encode()) + index) % 997) / 997 for index in range(8)]


class ModelRouter:
    def __init__(self):
        configured_name = (settings.model_provider or "").strip().lower()
        if settings.cloud_ai_enabled and configured_name in {"", "mock"}:
            configured_name = (settings.cloud_ai_provider or "gemini").strip().lower()
        self.provider_name = self._normalize_provider_name(configured_name)
        self.provider = self._create_provider()

    @staticmethod
    def _normalize_provider_name(name: str | None) -> str:
        value = (name or "mock").strip().lower()
        return value if value in {"mock", "ollama", "colibri", "gemini"} else "mock"

    def _create_provider(self, role: str = "general") -> ModelProvider:
        if self.provider_name == "ollama":
            return OllamaProvider(role=role)
        if self.provider_name == "colibri":
            return ColibriProvider()
        if self.provider_name == "gemini":
            return GeminiProvider()
        return MockProvider()

    @staticmethod
    def _normalize_role(role: str | None) -> str:
        value = (role or "general").strip().lower()
        if value not in MODEL_ROLES:
            raise ValueError(f"Unsupported model role: {value}")
        return value

    @staticmethod
    def is_datetime_request(text: str) -> bool:
        normalized = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
        return bool(
            re.search(r"\b(current|what is|whats|tell me)\b.*\b(date|time)\b", normalized)
            or re.search(r"\b(date|time)\b.*\b(current|now)\b", normalized)
            or "date and time" in normalized
        )

    @staticmethod
    def is_live_world_request(text: str) -> bool:
        if ModelRouter.is_datetime_request(text):
            return False
        normalized = re.sub(r"[^a-z0-9\s]+", " ", (text or "").lower()).strip()
        return any(
            re.search(rf"\b{re.escape(keyword)}\b", normalized)
            for keyword in _CURRENT_WORLD_KEYWORDS
        )

    @staticmethod
    def is_coding_request(text: str) -> bool:
        normalized = (text or "").lower()
        return bool(re.search(
            r"\b(?:build|fix|debug|implement|code|refactor|patch|"
            r"write a script|create app|resolve error|test this)\b",
            normalized,
        ))

    @staticmethod
    def is_vision_request(text: str) -> bool:
        normalized = (text or "").lower()
        return bool(re.search(
            r"\b(?:image|picture|photo|screenshot|vision)\b|"
            r"\b(?:what is|describe|analyze) this\b",
            normalized,
        ))

    @staticmethod
    def is_explicit_gemini_request(text: str) -> bool:
        return bool(re.search(
            r"\b(?:use|ask|send|route|switch to|with)\s+(?:google\s+)?gemini\b|"
            r"\bgemini\s*:",
            text or "",
            re.IGNORECASE,
        ))

    @staticmethod
    def is_safe_cloud_request(text: str) -> bool:
        return is_safe_public_cloud_text(text)

    @staticmethod
    def route_for_text(text: str) -> str:
        if not text or not text.strip():
            return "general"
        if ModelRouter.is_datetime_request(text):
            return "general"
        if ModelRouter.is_explicit_gemini_request(text):
            return "gemini"
        if ModelRouter.is_vision_request(text):
            return "vision"
        if ModelRouter.is_live_world_request(text):
            return "research"
        if ModelRouter.is_coding_request(text):
            return "coding"
        return "general"

    def _provider_for_role(self, role: str) -> ModelProvider:
        if role == "gemini":
            return GeminiProvider()
        if role == "research":
            return GeminiProvider()
        if role == "general" and self.provider_name == "gemini" and settings.cloud_ai_enabled:
            return self.provider
        if role == "general" or self.provider_name == "mock":
            return self.provider
        return self._create_provider(role)

    async def chat(
        self,
        messages: list[dict[str, str]],
        role: str | None = None,
        *,
        allow_cloud: bool = False,
        fast: bool = False,
    ) -> str:
        user_text = next(
            (
                item.get("content", "")
                for item in reversed(messages)
                if item.get("role") == "user"
            ),
            "",
        )
        role = self._normalize_role(role or self.route_for_text(user_text))

        cloud_route = (
            role in {"gemini", "research"}
            or (role == "general" and self.provider_name == "gemini")
        )
        if cloud_route and (allow_cloud or self.provider_name == "gemini"):
            if not settings.cloud_ai_enabled:
                raise RuntimeError("Cloud AI is disabled in configuration.")
            if (
                (role == "research" or self.is_live_world_request(user_text))
                and not settings.cloud_ai_search_grounding
            ):
                raise RuntimeError(
                    "Live research requires Google Search grounding to be enabled."
                )
            if not allow_cloud and self.provider_name == "gemini":
                raise CloudPrivacyError(
                    "Cloud routing is restricted to direct user requests."
                )
            if not is_safe_public_cloud_text(user_text):
                raise CloudPrivacyError(
                    "Cloud routing is blocked for private, sensitive, or non-text requests."
                )
            provider = self._provider_for_role(role)
            return final_model_response(
                await provider.chat(
                    [{"role": "user", "content": public_cloud_input(messages)}],
                    grounding=(
                        role == "research" or self.is_live_world_request(user_text)
                    ),
                )
            )

        if cloud_route and not allow_cloud and self.provider_name != "gemini":
            provider = self._provider_for_role(role)
            try:
                return final_model_response(await provider.chat(messages, **self._fast_options(fast)))
            except Exception:
                if (
                    self.provider_name == "ollama"
                    and role == "general"
                    and settings.cloud_ai_enabled
                    and is_safe_public_cloud_text(user_text)
                ):
                    return final_model_response(
                        await GeminiProvider().chat(
                            [{"role": "user", "content": public_cloud_input(messages)}],
                            grounding=False,
                        )
                    )
                raise

        provider = self._provider_for_role(role)
        try:
            return final_model_response(await provider.chat(messages, **self._fast_options(fast)))
        except Exception:
            if (
                self.provider_name == "ollama"
                and role == "general"
                and allow_cloud
                and settings.cloud_ai_enabled
                and is_safe_public_cloud_text(user_text)
            ):
                return final_model_response(
                    await GeminiProvider().chat(
                        [{"role": "user", "content": public_cloud_input(messages)}],
                        grounding=False,
                    )
                )
            raise

    @staticmethod
    def _fast_options(fast: bool) -> dict[str, object]:
        # qwen3 spends substantial time producing hidden reasoning. Voice
        # conversation needs a bounded direct answer, while normal chat keeps
        # the provider defaults unchanged.
        return {"think": False, "max_tokens": 256} if fast else {}

    async def embed(self, text: str, role: str = "embedding") -> list[float]:
        role = self._normalize_role(role)
        if role != "embedding":
            raise ValueError("Embedding calls must use the embedding role")
        if self.provider_name == "gemini":
            raise RuntimeError("Cloud embeddings are disabled to keep memory local.")
        provider = self._provider_for_role(role)
        return await provider.embed(text)

    async def vision_chat(self, prompt: str, image: bytes, mime_type: str) -> str:
        if not settings.vision_enabled:
            raise RuntimeError("Vision is disabled in configuration.")
        if self.provider_name != "ollama":
            raise RuntimeError("Ollama is unavailable for local vision.")
        if not image:
            raise ValueError("Vision requests require image input.")
        provider = self._create_provider("vision")
        vision_chat = getattr(provider, "vision_chat", None)
        if vision_chat is None:
            raise RuntimeError("The configured provider does not support vision.")
        return final_model_response(await vision_chat(prompt, image, mime_type))
