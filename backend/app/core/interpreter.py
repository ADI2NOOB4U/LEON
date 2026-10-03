from backend.app.core.router import ModelRouter
from pydantic import BaseModel
from backend.app.memory.memory import memory_service


class CommandIntent(BaseModel):
    intent: str
    title: str


class LeonInterpreter:
    def __init__(self):
        self.router = ModelRouter()

    async def interpret(self, message: str) -> CommandIntent:
        if self.router.provider_name == "mock":
            return self._fallback(message)

        prompt = f"""
Classify this user request.

Return ONLY valid JSON:
{{"intent":"task","title":"short task title"}}
or
{{"intent":"chat","title":""}}

Use "task" for requests that require Leon to do work.
Use "chat" for normal conversation.

REQUEST:
{message}
"""

        response = await self.router.chat([
            {"role": "system", "content": self._system_prompt(message)},
            {"role": "user", "content": prompt},
        ])

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            return CommandIntent.model_validate_json(response[start:end])
        except Exception:
            return self._fallback(message)

    @staticmethod
    def _system_prompt(message: str) -> str:
        prompt = "You are LEON command interpreter."
        context = memory_service.context_for(message)
        if context:
            prompt += "\nRelevant remembered context:\n" + context
        return prompt

    def _fallback(self, message: str) -> CommandIntent:
        words = (
            "build", "create", "make", "develop",
            "research", "analyze", "prepare",
            "run", "generate", "implement", "date", "time"
        )

        intent = (
            "task"
            if any(word in message.lower() for word in words)
            else "chat"
        )

        return CommandIntent(
            intent=intent,
            title=message if intent == "task" else "",
        )
