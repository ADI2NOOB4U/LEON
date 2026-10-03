from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.security.permissions import PermissionLevel, PermissionManager
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.system_tools import system_registry

router = APIRouter(prefix="/tools", tags=["Tools"])
registry: ToolRegistry = system_registry
permission_manager = PermissionManager()


class ToolExecutionRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False


@router.get("")
async def list_tools() -> list[dict[str, str]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "permission": tool.permission,
        }
        for tool in registry.list()
    ]


@router.post("/{tool_name}")
async def execute_tool(tool_name: str, request: ToolExecutionRequest) -> Any:
    tool = registry.get(tool_name)
    if tool is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown tool: {tool_name}",
        )

    try:
        permission = PermissionLevel(tool.permission)
    except (AttributeError, ValueError, TypeError):
        raise HTTPException(
            status_code=403,
            detail=f"Tool '{tool_name}' has an invalid permission level",
        ) from None

    if permission == PermissionLevel.BLOCKED:
        raise HTTPException(
            status_code=403,
            detail=f"Tool '{tool_name}' is blocked",
        )
    if permission == PermissionLevel.CONFIRM and not request.confirmed:
        raise HTTPException(
            status_code=403,
            detail=f"Confirmation required for tool '{tool_name}'",
        )
    if not permission_manager.can_execute(tool, confirmed=request.confirmed):
        raise HTTPException(
            status_code=403,
            detail=f"Tool '{tool_name}' cannot be executed",
        )

    try:
        return await registry.execute(tool_name, **request.arguments)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
