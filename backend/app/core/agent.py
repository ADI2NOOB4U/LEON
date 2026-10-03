from backend.app.core.capabilities import is_datetime_request
from backend.app.core.router import ModelRouter, final_model_response
from backend.app.memory.memory import memory_service
from backend.app.tools.system_tools import GetDatetimeTool, format_local_datetime


SYSTEM_PROMPT = """
You are LEON, a personal AI assistant.

You are being developed as a long-term personal AI system.

Behavior:
- Be useful and concise.
- Do not claim to have performed an action unless a tool actually performed it.
- Ask for confirmation before dangerous or destructive actions.
- Prefer factual answers over guesses.
- Keep responses natural and direct.
"""


class LeonAgent:

    def __init__(self):
        self.router = ModelRouter()

    async def _local_datetime_reply(self, user_message: str) -> str | None:
        if not is_datetime_request(user_message):
            return None
        payload = await GetDatetimeTool().execute()
        return format_local_datetime(payload)

    async def chat(self, user_message: str) -> str:
        datetime_reply = await self._local_datetime_reply(user_message)
        if datetime_reply is not None:
            return datetime_reply
        route_for_text = getattr(self.router, "route_for_text", None)
        role = route_for_text(user_message) if route_for_text else "general"
        system_prompt = SYSTEM_PROMPT.strip()
        memory_context = memory_service.context_for(user_message)
        if memory_context and role not in {"gemini", "research"}:
            system_prompt += (
                "\n\nRelevant remembered context (use only when relevant; do not "
                "invent or expose other memories):\n" + memory_context
            )

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ]

        return final_model_response(
            await self._chat_with_role(
                messages,
                role,
                allow_cloud=ModelRouter.is_safe_cloud_request(user_message),
            )
        )

    async def chat_fast(self, user_message: str) -> str:
        """Low-overhead local conversation path used by voice turns."""
        datetime_reply = await self._local_datetime_reply(user_message)
        if datetime_reply is not None:
            return datetime_reply
        route_for_text = getattr(self.router, "route_for_text", None)
        role = route_for_text(user_message) if route_for_text else "general"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {"role": "user", "content": user_message},
        ]
        return final_model_response(
            await self._chat_with_role(
                messages,
                role,
                allow_cloud=ModelRouter.is_safe_cloud_request(user_message),
                fast=True,
            )
        )

    async def _chat_with_role(
        self, messages: list[dict[str, str]], role: str, allow_cloud: bool,
        fast: bool = False,
    ) -> str:
        """Keep simple legacy test doubles compatible with explicit routing."""
        try:
            return await self.router.chat(
                messages, role=role, allow_cloud=allow_cloud, fast=fast
            )
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            if "allow_cloud" in str(exc):
                try:
                    return await self.router.chat(messages, role=role)
                except TypeError as role_exc:
                    if "unexpected keyword argument" not in str(role_exc):
                        raise
                    return await self.router.chat(messages)
            if "fast" in str(exc):
                return await self.router.chat(messages, role=role, allow_cloud=allow_cloud)
            return await self.router.chat(messages)
