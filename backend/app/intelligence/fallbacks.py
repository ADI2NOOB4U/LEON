from __future__ import annotations


def unavailable_message(provider: str, capability: str) -> str:
    return f"{capability} is unavailable because provider {provider} is not ready."
