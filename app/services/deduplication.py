from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job
from app.db.repositories.jobs import find_duplicate, insert_job
from app.domain.models import NormalizedJob


async def persist_if_new(session: AsyncSession, job: NormalizedJob) -> tuple[Job, bool]:
    existing = await find_duplicate(session, job)
    if existing:
        return existing, False
    created = await insert_job(session, job)
    return created, True
