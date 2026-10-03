from typing import Any

from .base import BaseTool


class ToolRegistry:
    """In-memory registry for LEON tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool by its name."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """Return a registered tool, or ``None`` when it is unknown."""
        return self._tools.get(name)

    def list(self) -> list[BaseTool]:
        """Return registered tools in registration order."""
        return list(self._tools.values())

    async def execute(self, name: str, **kwargs: Any) -> Any:
        """Execute a registered tool by name."""
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        return await tool.execute(**kwargs)
