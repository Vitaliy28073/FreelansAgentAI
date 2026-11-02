from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.connectors.base import BaseConnector
from app.connectors.cursor import select_new_jobs
from app.connectors.http_safety import request_with_backoff, strip_html
from app.core.config import Settings
from app.core.exceptions import AuthRequiredError, SchemaChangedError
from app.core.security import canonical_url, content_hash
from app.domain.enums import SourceCode
from app.domain.models import (
    ConnectorHealth,
    NormalizedBudget,
    NormalizedJob,
    RateLimitState,
    RawJob,
)


class FreelancehuntConnector(BaseConnector):
    code = SourceCode.FREELANCEHUNT
    access_method = "api"

    def __init__(
        self,
        settings: Settings,
        token: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._token = token
        self._client = client
        self._owns_client = client is None
        self._rate = RateLimitState()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Accept-Language": "ru",
        }

    async def _client_obj(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._settings.http_timeout_seconds,
                headers={"User-Agent": "FreelanceRadarAI/0.1 (+official API client)"},
                follow_redirects=True,
            )
        return self._client

    def _capture_rate_limit(self, response: httpx.Response) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        limit = response.headers.get("X-RateLimit-Limit")
        self._rate = RateLimitState(
            remaining=int(remaining) if remaining and remaining.isdigit() else None,
            limit=limit,
        )

    async def health_check(self) -> ConnectorHealth:
        if not self._token:
            raise AuthRequiredError("Freelancehunt token is not configured")
        client = await self._client_obj()
        response = await request_with_backoff(
            client,
            "GET",
            f"{self._settings.freelancehunt_base_url}/my/profile",
            headers=self._headers(),
            max_retries=1,
        )
        self._capture_rate_limit(response)
        return ConnectorHealth(
            source=self.code,
            healthy=True,
            status="ok",
            detail="profile reachable",
        )

    async def fetch_new_jobs(
        self, cursor: dict[str, Any] | None, limit: int
    ) -> tuple[list[RawJob], dict[str, Any]]:
        if not self._token:
            raise AuthRequiredError("Freelancehunt token is not configured")
        client = await self._client_obj()
        response = await request_with_backoff(
            client,
            "GET",
            f"{self._settings.freelancehunt_base_url}/projects",
            headers=self._headers(),
            params={"page[number]": 1},
            max_retries=self._settings.http_max_retries,
        )
        self._capture_rate_limit(response)
        payload = response.json()
        data = payload.get("data")
        if not isinstance(data, list):
            raise SchemaChangedError("Freelancehunt projects response is missing data[]")

        raw_jobs = [self._item_to_raw(item) for item in data]
        return select_new_jobs(raw_jobs, cursor, limit)

    def get_rate_limit_state(self) -> RateLimitState:
        return self._rate

    def normalize(self, raw_item: RawJob) -> NormalizedJob:
        attrs = raw_item.payload.get("attributes") or {}
        budget_raw = attrs.get("budget") or {}
        budget = NormalizedBudget(
            amount=float(budget_raw["amount"]) if budget_raw.get("amount") is not None else None,
            currency=budget_raw.get("currency"),
            raw=str(budget_raw) if budget_raw else None,
        )
        skills = [str(item.get("name")) for item in attrs.get("skills") or [] if item.get("name")]
        description = strip_html(str(attrs.get("description") or raw_item.description))
        title = str(attrs.get("name") or raw_item.title)
        canon = canonical_url(raw_item.url)
        return NormalizedJob(
            source=self.code,
            external_id=raw_item.external_id,
            url=raw_item.url,
            canonical_url=canon,
            title=title,
            description=description,
            category=", ".join(skills) or None,
            skills=skills,
            budget=budget,
            published_at=raw_item.published_at,
            discovered_at=datetime.now(timezone.utc),
            bid_count=attrs.get("bid_count"),
            language="ru",
            content_hash=content_hash(title, description, budget.raw),
            extras={
                "is_premium": attrs.get("is_premium"),
                "is_only_for_plus": attrs.get("is_only_for_plus"),
                "safe_type": attrs.get("safe_type"),
                "employer_login": (attrs.get("employer") or {}).get("login"),
            },
        )

    def _item_to_raw(self, item: dict[str, Any]) -> RawJob:
        if "id" not in item or "attributes" not in item:
            raise SchemaChangedError("Freelancehunt project item is missing id/attributes")
        attrs = item["attributes"]
        links = item.get("links") or {}
        web = ((links.get("self") or {}) if isinstance(links.get("self"), dict) else {}).get("web")
        url = web or f"https://freelancehunt.com/project/{item['id']}.html"
        published = None
        if attrs.get("published_at"):
            published = datetime.fromisoformat(str(attrs["published_at"]).replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
        return RawJob(
            source=self.code,
            external_id=str(item["id"]),
            url=url,
            title=str(attrs.get("name") or ""),
            description=str(attrs.get("description") or ""),
            category=None,
            published_at=published,
            payload=item,
        )

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
