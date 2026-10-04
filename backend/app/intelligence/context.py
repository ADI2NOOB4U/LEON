from __future__ import annotations

from typing import Any


class ContextManager:
    """Selective context container; callers opt in to each context source."""
    def build(self, *, conversation: list[dict[str, Any]] | None = None,
              ui_section: str | None = None, active_task: dict[str, Any] | None = None,
              media_state: dict[str, Any] | None = None, memory: list[str] | None = None,
              permissions: dict[str, Any] | None = None,
              provider_availability: dict[str, bool] | None = None) -> dict[str, Any]:
        return {key: value for key, value in {
            "conversation": conversation, "ui_section": ui_section,
            "active_task": active_task, "media_state": media_state,
            "memory": memory, "permissions": permissions,
            "provider_availability": provider_availability,
        }.items() if value is not None}
