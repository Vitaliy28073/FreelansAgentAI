from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from app.connectors.base import BaseConnector
from app.connectors.cursor import select_new_jobs
from app.connectors.http_safety import request_with_backoff, strip_html
from app.core.config import Settings
from app.core.exceptions import SchemaChangedError
from app.core.security import canonical_url, content_hash
from app.domain.enums import SourceCode
from app.domain.models import (
    ConnectorHealth,
    NormalizedBudget,
    NormalizedJob,
    RateLimitState,
    RawJob,
)

BUDGET_RE = re.compile(
    r"Бюджет:\s*([\d\s]+)\s*(?:&#8381;|₽|руб|RUB)?",
    re.IGNORECASE,
)
PROJECT_ID_RE = re.compile(r"/projects/(\d+)/")


class FlRssConnector(BaseConnector):
    code = SourceCode.FL_RSS
    access_method = "rss"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._owns_client = client is None
        self._rate = RateLimitState()

    async def _client_obj(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._settings.http_timeout_seconds,
                headers={"User-Agent": "FreelanceRadarAI/0.1 (+personal RSS reader)"},
                follow_redirects=True,
            )
        return self._client

    async def health_check(self) -> ConnectorHealth:
        client = await self._client_obj()
        response = await request_with_backoff(
            client, "GET", self._settings.fl_rss_url, max_retries=1
        )
        parsed = feedparser.parse(response.text)
        healthy = bool(parsed.entries)
        return ConnectorHealth(
            source=self.code,
            healthy=healthy,
            status="ok" if healthy else "empty",
            detail=parsed.feed.get("title") if hasattr(parsed, "feed") else None,
        )

    async def fetch_new_jobs(
        self, cursor: dict[str, Any] | None, limit: int
    ) -> tuple[list[RawJob], dict[str, Any]]:
        client = await self._client_obj()
        response = await request_with_backoff(
            client,
            "GET",
            self._settings.fl_rss_url,
            max_retries=self._settings.http_max_retries,
        )
        parsed = feedparser.parse(response.text)
        if not getattr(parsed, "entries", None) and "rss" not in response.text.lower():
            raise SchemaChangedError("FL.ru RSS did not contain a recognizable feed")

        raw_jobs = [self._entry_to_raw(entry) for entry in parsed.entries]
        return select_new_jobs(raw_jobs, cursor, limit)

    def get_rate_limit_state(self) -> RateLimitState:
        return self._rate

    def normalize(self, raw_item: RawJob) -> NormalizedJob:
        title, budget = self._split_budget(raw_item.title)
        description = strip_html(html.unescape(raw_item.description))
        canon = canonical_url(raw_item.url)
        discovered = datetime.now(timezone.utc)
        skills = []
        if raw_item.category:
            skills = [part.strip() for part in raw_item.category.split("/") if part.strip()]
        return NormalizedJob(
            source=self.code,
            external_id=raw_item.external_id,
            url=raw_item.url,
            canonical_url=canon,
            title=title,
            description=description,
            category=raw_item.category,
            skills=skills,
            budget=budget,
            published_at=raw_item.published_at,
            discovered_at=discovered,
            language="ru",
            content_hash=content_hash(title, description, budget.raw),
            extras={"guid": raw_item.payload.get("guid")},
        )

    def _entry_to_raw(self, entry: Any) -> RawJob:
        link = html.unescape(getattr(entry, "link", "") or "")
        guid = html.unescape(getattr(entry, "id", "") or link)
        match = PROJECT_ID_RE.search(link) or PROJECT_ID_RE.search(guid)
        if not match:
            raise SchemaChangedError("FL.ru RSS item is missing a project id in URL")
        published = None
        if getattr(entry, "published", None):
            try:
                published = parsedate_to_datetime(entry.published).astimezone(timezone.utc)
            except (TypeError, ValueError):
                published = None
        return RawJob(
            source=self.code,
            external_id=match.group(1),
            url=link,
            title=html.unescape(getattr(entry, "title", "") or ""),
            description=html.unescape(getattr(entry, "summary", "") or getattr(entry, "description", "") or ""),
            category=html.unescape(getattr(entry, "category", "") or "") or None,
            published_at=published,
            payload={"guid": guid},
        )

    def _split_budget(self, title: str) -> tuple[str, NormalizedBudget]:
        clean_title = html.unescape(title).replace("&#8381;", "₽")
        match = BUDGET_RE.search(clean_title)
        budget = NormalizedBudget()
        if match:
            raw_amount = re.sub(r"\s+", "", match.group(1))
            try:
                budget.amount = float(raw_amount)
                budget.currency = "RUB"
                budget.raw = match.group(0)
            except ValueError:
                budget.raw = match.group(0)
            clean_title = BUDGET_RE.sub("", clean_title)
        clean_title = re.sub(r"\s*\((?:для всех)?\s*\)\s*$", "", clean_title)
        return clean_title.strip(" -–,"), budget

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
