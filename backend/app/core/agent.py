from backend.app.core.router import ModelRouter


from backend.app.memory.memory import memory_service


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

    async def chat(self, user_message: str) -> str:

        system_prompt = SYSTEM_PROMPT.strip()
        memory_context = memory_service.context_for(user_message)
        if memory_context:
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

        return await self.router.chat(messages)
