from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, JobAnalysis, JobSource, JobUserState, ResponseDraft
from app.domain.models import NormalizedJob


async def find_duplicate(session: AsyncSession, job: NormalizedJob) -> Job | None:
    result = await session.execute(
        select(Job).where(
            (Job.source == job.source.value) & (Job.external_id == job.external_id)
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    result = await session.execute(select(Job).where(Job.canonical_url == job.canonical_url))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    result = await session.execute(select(Job).where(Job.content_hash == job.content_hash))
    return result.scalar_one_or_none()


async def insert_job(session: AsyncSession, job: NormalizedJob) -> Job:
    record = Job(
        source=job.source.value,
        external_id=job.external_id,
        url=str(job.url),
        canonical_url=job.canonical_url,
        title=job.title,
        description=job.description,
        category=job.category,
        skills=job.skills,
        budget_amount=job.budget.amount,
        budget_currency=job.budget.currency,
        budget_raw=job.budget.raw,
        published_at=job.published_at,
        discovered_at=job.discovered_at,
        bid_count=job.bid_count,
        language=job.language,
        content_hash=job.content_hash,
        extras=job.extras,
        status="new",
    )
    session.add(record)
    await session.flush()
    session.add(
        JobSource(
            job_id=record.id,
            source=job.source.value,
            external_id=job.external_id,
            url=str(job.url),
        )
    )
    return record


async def get_job(session: AsyncSession, job_id: int) -> Job | None:
    result = await session.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def get_or_create_user_state(
    session: AsyncSession, user_id: int, job_id: int
) -> JobUserState:
    result = await session.execute(
        select(JobUserState).where(
            JobUserState.user_id == user_id, JobUserState.job_id == job_id
        )
    )
    state = result.scalar_one_or_none()
    if state:
        return state
    state = JobUserState(user_id=user_id, job_id=job_id)
    session.add(state)
    await session.flush()
    return state


async def list_recent_jobs(
    session: AsyncSession, user_id: int, *, limit: int = 10, favorites: bool = False
) -> list[tuple[Job, JobUserState]]:
    stmt: Select[tuple[Job, JobUserState]] = (
        select(Job, JobUserState)
        .join(JobUserState, JobUserState.job_id == Job.id)
        .where(JobUserState.user_id == user_id)
        .order_by(Job.discovered_at.desc())
        .limit(limit)
    )
    if favorites:
        stmt = stmt.where(JobUserState.favorite.is_(True))
    result = await session.execute(stmt)
    return list(result.all())


async def save_analysis(
    session: AsyncSession,
    *,
    job_id: int,
    user_id: int,
    provider: str,
    model: str,
    result: dict,
    score: int,
    risk_penalty: int,
    decision: str,
    confidence: float,
    summary: str,
    fallback: bool,
) -> JobAnalysis:
    analysis = JobAnalysis(
        job_id=job_id,
        user_id=user_id,
        provider=provider,
        model=model,
        result=result,
        score=score,
        risk_penalty=risk_penalty,
        decision=decision,
        confidence=confidence,
        summary=summary,
        fallback=fallback,
    )
    session.add(analysis)
    await session.flush()
    return analysis


async def latest_analysis(
    session: AsyncSession, job_id: int, user_id: int
) -> JobAnalysis | None:
    result = await session.execute(
        select(JobAnalysis)
        .where(JobAnalysis.job_id == job_id, JobAnalysis.user_id == user_id)
        .order_by(JobAnalysis.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def save_drafts(
    session: AsyncSession, job_id: int, user_id: int, drafts: list[dict]
) -> list[ResponseDraft]:
    records: list[ResponseDraft] = []
    for item in drafts:
        record = ResponseDraft(
            job_id=job_id,
            user_id=user_id,
            style=item["style"],
            body=item["body"],
            used_profile_facts=item.get("used_profile_facts", []),
            missing_facts=item.get("missing_facts", []),
        )
        session.add(record)
        records.append(record)
    await session.flush()
    return records


async def list_drafts(
    session: AsyncSession, job_id: int, user_id: int
) -> list[ResponseDraft]:
    result = await session.execute(
        select(ResponseDraft)
        .where(ResponseDraft.job_id == job_id, ResponseDraft.user_id == user_id)
        .order_by(ResponseDraft.id.desc())
    )
    return list(result.scalars().all())


async def count_today_notifications(session: AsyncSession, user_id: int) -> int:
    from app.db.models import NotificationEvent

    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(func.count(NotificationEvent.id)).where(
            NotificationEvent.user_id == user_id,
            NotificationEvent.created_at >= start,
            NotificationEvent.status == "sent",
        )
    )
    return int(result.scalar_one() or 0)
