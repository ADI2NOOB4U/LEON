import re

from backend.app.core.router import ModelRouter
from pydantic import BaseModel, Field
from backend.app.memory.memory import memory_service
from backend.app.core.capabilities import Capability, CapabilityIntent, classify_command, is_datetime_request, is_system_state_request


class CommandIntent(BaseModel):
    intent: str
    title: str
    task_type: str = "standard"
    capability: str = Capability.CHAT.value
    action: str = "chat"
    arguments: dict[str, str] = Field(default_factory=dict)
    requires_confirmation: bool = False
    is_mission: bool = False


class LeonInterpreter:
    def __init__(self):
        self.router = ModelRouter()

    async def interpret(self, message: str) -> CommandIntent:
        proposal = classify_command(message)
        if proposal.capability == Capability.DATETIME or is_datetime_request(message):
            return CommandIntent(
                intent="action",
                title=message,
                task_type="standard",
                capability=Capability.DATETIME.value,
                action="current",
                arguments={},
            )
        if proposal.capability == Capability.SYSTEM_STATE or is_system_state_request(message):
            return CommandIntent(
                intent="action",
                title=message,
                task_type="standard",
                capability=Capability.SYSTEM_STATE.value,
                action="status",
                arguments={},
            )
        if self._is_simple_chat(message):
            return CommandIntent(intent="chat", title="")
        if proposal.capability != Capability.CHAT:
            return self._fallback(message, proposal)
        fallback = self._fallback(message, proposal)
        # Normal conversation does not need a model call just to decide that
        # it is conversation. Keep the model classifier for task-like or
        # ambiguous requests where it can still improve intent selection.
        if fallback.intent == "chat" or self.router.provider_name == "mock":
            return fallback

        prompt = f"""
Classify this user request.

Return ONLY valid JSON:
{{"intent":"task","title":"short task title","task_type":"standard"}}
or
{{"intent":"chat","title":"","task_type":"standard"}}

Use "task" for requests that require Leon to do work.
Use "chat" for normal conversation.
Use task_type "research" for web search, current/latest/news, source comparison, or deep research requests.

REQUEST:
{message}
"""

        response = await self.router.chat(
            [
                {"role": "system", "content": self._system_prompt(message)},
                {"role": "user", "content": prompt},
            ],
            role="general",
            allow_cloud=ModelRouter.is_safe_cloud_request(message),
        )

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            return CommandIntent.model_validate_json(response[start:end])
        except Exception:
            fallback = self._fallback(message, proposal)
            return fallback

    @staticmethod
    def _is_simple_chat(message: str) -> bool:
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        return bool(
            re.fullmatch(r"(?:hi|hello|hey)(?: leon)?", normalized)
            or re.fullmatch(r"(?:what|who) are you", normalized)
        )

    @staticmethod
    def _system_prompt(message: str) -> str:
        prompt = "You are LEON command interpreter."
        context = memory_service.context_for(message)
        if context:
            prompt += "\nRelevant remembered context:\n" + context
        return prompt

    def _fallback(self, message: str, proposal: CapabilityIntent | None = None) -> CommandIntent:
        proposal = proposal or classify_command(message)
        words = (
            "build", "create", "make", "develop",
            "research", "analyze", "prepare",
            "run", "generate", "implement", "date", "time",
            "search", "latest", "current", "recent", "today", "happened",
        )

        intent = "task" if proposal.capability != Capability.CHAT or any(
            word in message.lower() for word in words
        ) else "chat"
        research_terms = (
            "search the web", "search online", "latest", "current news", "today's news",
            "research", "deep research", "compare sources", "look up", "find multiple sources",
            "what happened today", "recent",
        )

        return CommandIntent(
            intent=intent,
            title=message if intent == "task" else "",
            task_type=("research" if intent == "task" and any(
                term in message.lower() for term in research_terms
            ) else "standard"),
            capability=proposal.capability.value,
            action=proposal.action,
            arguments=proposal.arguments,
            requires_confirmation=proposal.requires_confirmation,
            is_mission=self._looks_like_mission(message),
        )

    @staticmethod
    def _looks_like_mission(message: str) -> bool:
        value = message.lower()
        verbs = sum(bool(re.search(rf"\b{word}\b", value)) for word in ("build", "create", "implement", "test", "fix", "repair", "inspect", "research"))
        return verbs >= 2 or bool(re.search(r"\b(keep fixing|until it works|when it is done|when done)\b", value))
