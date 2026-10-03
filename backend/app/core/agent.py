from backend.app.core.router import ModelRouter


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

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.strip(),
            },
            {
                "role": "user",
                "content": user_message,
            },
        ]

        return await self.router.chat(messages)
