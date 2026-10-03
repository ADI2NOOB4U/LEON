from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Base interface for tools available to LEON."""

    name: str
    description: str
    permission: str

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with the supplied arguments."""
        raise NotImplementedError
