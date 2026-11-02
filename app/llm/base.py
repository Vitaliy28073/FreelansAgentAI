from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    async def complete_json(self, *, system: str, user: str) -> str:
        raise NotImplementedError
