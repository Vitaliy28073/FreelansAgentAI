from __future__ import annotations

import httpx
import pytest

from app.connectors.freelancehunt_api import FreelancehuntConnector
from app.core.config import Settings
from app.core.exceptions import AuthRequiredError


@pytest.mark.asyncio
async def test_freelancehunt_normalize(fh_payload: dict) -> None:
    settings = Settings(freelancehunt_poll_seconds=60)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=fh_payload, headers={"X-RateLimit-Remaining": "1190", "X-RateLimit-Limit": "1200 per hour"}))
    async with httpx.AsyncClient(transport=transport) as client:
        connector = FreelancehuntConnector(settings, token="test-token", client=client)
        jobs, cursor = await connector.fetch_new_jobs({"bootstrapped": True}, 10)
    assert len(jobs) == 1
    job = connector.normalize(jobs[0])
    assert job.external_id == "299165"
    assert job.budget.amount == 2300
    assert job.budget.currency == "UAH"
    assert "Python" in job.skills
    assert job.bid_count == 1
    assert "299165" in cursor["seen_ids"]
    assert connector.get_rate_limit_state().remaining == 1190


@pytest.mark.asyncio
async def test_freelancehunt_requires_token() -> None:
    connector = FreelancehuntConnector(Settings(freelancehunt_poll_seconds=60), token="")
    with pytest.raises(AuthRequiredError):
        await connector.fetch_new_jobs({}, 10)
