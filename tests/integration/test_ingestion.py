from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import select

from app.connectors.base import BaseConnector
from app.connectors.cursor import select_new_jobs
from app.core.security import content_hash
from app.db.models import Job, JobAnalysis, NotificationEvent, SourceConnector, User
from app.db.repositories.users import get_or_create_user
from app.domain.enums import SourceCode
from app.domain.models import (
    ConnectorHealth,
    NormalizedBudget,
    NormalizedJob,
    RateLimitState,
    RawJob,
)
from app.services.analysis_service import AnalysisService
from app.services.deduplication import persist_if_new
from app.services.ingestion import IngestionService


def _norm(external_id: str, title: str = "Python API") -> NormalizedJob:
    desc = "Нужен Python разработчик"
    return NormalizedJob(
        source=SourceCode.FL_RSS,
        external_id=external_id,
        url=f"https://www.fl.ru/projects/{external_id}/python-api.html",
        canonical_url=f"https://www.fl.ru/projects/{external_id}/python-api.html",
        title=title,
        description=desc,
        category="Программирование",
        skills=["Python"],
        budget=NormalizedBudget(amount=10000, currency="RUB", raw="10000"),
        published_at=datetime.now(timezone.utc),
        discovered_at=datetime.now(timezone.utc),
        content_hash=content_hash(title, desc, "10000"),
    )


@pytest.mark.asyncio
async def test_dedup_after_restart(session) -> None:
    job = _norm("100")
    first, created = await persist_if_new(session, job)
    assert created is True
    second, created_again = await persist_if_new(session, job)
    assert created_again is False
    assert first.id == second.id
    rows = (await session.execute(select(Job))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_user_isolation_and_delete(session) -> None:
    user = await get_or_create_user(session, 42, "owner")
    assert user.profile is not None
    again = await get_or_create_user(session, 42, "owner")
    assert again.id == user.id
    count = (await session.execute(select(User))).scalars().all()
    assert len(count) == 1


class _StubConnector(BaseConnector):
    code = SourceCode.FL_RSS
    access_method = "rss"

    def __init__(self, jobs: list[RawJob]) -> None:
        self._jobs = jobs
        self.calls: list[dict[str, Any] | None] = []

    async def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(source=self.code, healthy=True, status="ok")

    async def fetch_new_jobs(
        self, cursor: dict[str, Any] | None, limit: int
    ) -> tuple[list[RawJob], dict[str, Any]]:
        self.calls.append(cursor)
        return select_new_jobs(self._jobs, cursor, limit)

    def get_rate_limit_state(self) -> RateLimitState:
        return RateLimitState()

    def normalize(self, raw_item: RawJob) -> NormalizedJob:
        return _norm(raw_item.external_id, raw_item.title)


def _raw(external_id: str, title: str = "Python API") -> RawJob:
    return RawJob(
        source=SourceCode.FL_RSS,
        external_id=external_id,
        url=f"https://www.fl.ru/projects/{external_id}/python-api.html",
        title=title,
        description="Нужен Python разработчик",
        published_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_first_poll_bootstraps_without_ai_or_telegram(session, settings) -> None:
    user = await get_or_create_user(session, 7, "owner")
    source = SourceConnector(
        user_id=user.id,
        code=SourceCode.FL_RSS.value,
        enabled=True,
        status="enabled",
        access_method="rss",
        cursor={},
    )
    session.add(source)
    await session.flush()

    notifications: list[tuple] = []

    async def notify(owner, job, analysis, text: str | None = None) -> int | None:
        notifications.append((owner, job, analysis, text))
        return 1

    service = IngestionService(settings, AnalysisService(None), notify)
    connector = _StubConnector([_raw("201"), _raw("202")])
    run = await service.run_connector(
        session, connector=connector, user=user, source_row=source, profile=user.profile
    )

    assert run.fetched == 2
    assert source.cursor["bootstrapped"] is True
    assert set(source.cursor["seen_ids"]) == {"201", "202"}
    assert (await session.execute(select(Job))).scalars().all() == []
    assert (await session.execute(select(JobAnalysis))).scalars().all() == []
    assert (await session.execute(select(NotificationEvent))).scalars().all() == []
    assert len(notifications) == 1
    assert notifications[0][1] is None
    assert "инициализирован" in (notifications[0][3] or "")


@pytest.mark.asyncio
async def test_second_poll_analyzes_only_new_jobs(session, settings) -> None:
    user = await get_or_create_user(session, 8, "owner")
    user.full_monitoring = True
    source = SourceConnector(
        user_id=user.id,
        code=SourceCode.FL_RSS.value,
        enabled=True,
        status="enabled",
        access_method="rss",
        cursor={"bootstrapped": True, "seen_ids": ["201"], "last_published": None},
    )
    session.add(source)
    await session.flush()

    notifications: list[tuple] = []

    async def notify(owner, job, analysis, text: str | None = None) -> int | None:
        notifications.append((job.id if job else None, text))
        return 11

    service = IngestionService(settings, AnalysisService(None), notify)
    connector = _StubConnector([_raw("201"), _raw("303", "Python FastAPI")])
    run = await service.run_connector(
        session, connector=connector, user=user, source_row=source, profile=user.profile
    )

    jobs = (await session.execute(select(Job))).scalars().all()
    analyses = (await session.execute(select(JobAnalysis))).scalars().all()
    assert run.inserted == 1
    assert run.duplicates == 0
    assert len(jobs) == 1
    assert jobs[0].external_id == "303"
    assert len(analyses) == 1
    assert len(notifications) == 1
    assert notifications[0][0] == jobs[0].id
