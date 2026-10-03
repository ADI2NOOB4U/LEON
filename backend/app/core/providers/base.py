from abc import ABC, abstractmethod
from typing import Any


class ModelProvider(ABC):

    @abstractmethod
    async def chat(self, messages: list[dict[str, str]]) -> str:
        raise NotImplementedError
