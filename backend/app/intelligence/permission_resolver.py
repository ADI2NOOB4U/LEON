from __future__ import annotations

from backend.app.core.action_authority import ActionAuthority


def resolve_permission(authority: ActionAuthority, tool_name: str) -> str:
    tool = authority.registry.get(tool_name)
    return getattr(tool, "permission", "BLOCKED") if tool else "BLOCKED"
