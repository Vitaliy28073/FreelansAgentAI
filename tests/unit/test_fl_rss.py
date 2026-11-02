from __future__ import annotations

import httpx
import pytest

from app.connectors.fl_rss import FlRssConnector
from app.connectors.http_safety import classify_response
from app.core.config import Settings
from app.core.exceptions import ChallengeDetectedError, ForbiddenError, RateLimitedError


def _settings() -> Settings:
    return Settings(fl_rss_url="https://www.fl.ru/rss/all.xml", fl_rss_poll_seconds=120)


@pytest.mark.asyncio
async def test_fl_rss_normalize_budget_and_id(fl_rss_xml: str) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text=fl_rss_xml, headers={"content-type": "application/rss+xml"})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        connector = FlRssConnector(_settings(), client=client)
        jobs, cursor = await connector.fetch_new_jobs({"bootstrapped": True}, 10)
    assert len(jobs) == 2
    assert jobs[0].external_id == "5527001"
    normalized = connector.normalize(jobs[0])
    assert normalized.budget.amount == 25000
    assert normalized.budget.currency == "RUB"
    assert "Бюджет" not in normalized.title
    assert normalized.canonical_url.endswith("/python-fastapi-bot-dlya-telegram.html")
    assert "5527001" in cursor["seen_ids"]


@pytest.mark.asyncio
async def test_fl_rss_cursor_skips_seen(fl_rss_xml: str) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text=fl_rss_xml, headers={"content-type": "application/rss+xml"})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        connector = FlRssConnector(_settings(), client=client)
        first, cursor = await connector.fetch_new_jobs({}, 10)
        second, _ = await connector.fetch_new_jobs(cursor, 10)
    assert first == []
    assert cursor["bootstrapped"] is True
    assert "5527001" in cursor["seen_ids"]
    assert second == []


def test_http_safety_codes() -> None:
    classify_response(httpx.Response(200, text="ok"))
    with pytest.raises(ForbiddenError):
        classify_response(httpx.Response(403, text="no"))
    with pytest.raises(RateLimitedError) as exc:
        classify_response(httpx.Response(429, text="slow", headers={"Retry-After": "12"}))
    assert exc.value.retry_after == 12
    with pytest.raises(ChallengeDetectedError):
        classify_response(
            httpx.Response(200, text="<html>please solve captcha recaptcha</html>", headers={"content-type": "text/html"})
        )
