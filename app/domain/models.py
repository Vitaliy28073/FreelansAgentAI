from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from app.domain.enums import SourceCode


class RawJob(BaseModel):
    source: SourceCode
    external_id: str
    url: str
    title: str
    description: str = ""
    category: str | None = None
    published_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class NormalizedBudget(BaseModel):
    amount: float | None = None
    currency: str | None = None
    raw: str | None = None


class NormalizedJob(BaseModel):
    source: SourceCode
    external_id: str
    url: HttpUrl | str
    canonical_url: str
    title: str
    description: str
    category: str | None = None
    skills: list[str] = Field(default_factory=list)
    budget: NormalizedBudget = Field(default_factory=NormalizedBudget)
    published_at: datetime | None = None
    discovered_at: datetime
    bid_count: int | None = None
    language: str | None = "ru"
    content_hash: str
    extras: dict[str, Any] = Field(default_factory=dict)


class FilterResult(BaseModel):
    passed: bool
    reasons: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)


class ConnectorHealth(BaseModel):
    source: SourceCode
    healthy: bool
    status: str
    detail: str | None = None
    last_success_at: datetime | None = None


class RateLimitState(BaseModel):
    remaining: int | None = None
    limit: str | None = None
    retry_after: float | None = None
