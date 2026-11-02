from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import FreelancerProfile, User


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(
        select(User).options(selectinload(User.profile)).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession, telegram_id: int, username: str | None = None
) -> User:
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        if username and user.username != username:
            user.username = username
        return user
    user = User(telegram_id=telegram_id, username=username)
    session.add(user)
    await session.flush()
    profile = FreelancerProfile(user_id=user.id)
    session.add(profile)
    await session.flush()
    user.profile = profile
    return user


async def list_active_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).options(selectinload(User.profile)).where(User.deleted_at.is_(None))
    )
    return list(result.scalars().all())


async def delete_user_data(session: AsyncSession, user: User) -> None:
    from app.db.models import (
        AuditEvent,
        Feedback,
        JobAnalysis,
        JobUserState,
        NotificationEvent,
        OutreachEvent,
        ResponseDraft,
        SourceConnector,
        SourceCredential,
    )

    connector_ids = (
        await session.execute(select(SourceConnector.id).where(SourceConnector.user_id == user.id))
    ).scalars().all()
    if connector_ids:
        creds = (
            await session.execute(
                select(SourceCredential).where(SourceCredential.connector_id.in_(connector_ids))
            )
        ).scalars().all()
        for cred in creds:
            await session.delete(cred)
    for model in (
        SourceConnector,
        JobAnalysis,
        ResponseDraft,
        OutreachEvent,
        Feedback,
        NotificationEvent,
        JobUserState,
        AuditEvent,
        FreelancerProfile,
    ):
        rows = (
            await session.execute(select(model).where(model.user_id == user.id))  # type: ignore[attr-defined]
        ).scalars().all()
        for row in rows:
            await session.delete(row)
    await session.delete(user)
