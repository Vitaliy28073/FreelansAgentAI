from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.domain.enums import SourceCode
from app.domain.models import ConnectorHealth, NormalizedJob, RateLimitState, RawJob


class BaseConnector(ABC):
    code: SourceCode
    access_method: str

    @abstractmethod
    async def health_check(self) -> ConnectorHealth:
        raise NotImplementedError

    @abstractmethod
    async def fetch_new_jobs(
        self, cursor: dict[str, Any] | None, limit: int
    ) -> tuple[list[RawJob], dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_rate_limit_state(self) -> RateLimitState:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw_item: RawJob) -> NormalizedJob:
        raise NotImplementedError

    async def close(self) -> None:
        return None
