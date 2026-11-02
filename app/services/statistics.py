from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobAnalysis, JobUserState, NotificationEvent, OutreachEvent, ResponseDraft


async def user_stats(session: AsyncSession, user_id: int) -> dict[str, int]:
    async def count(model, extra=None) -> int:  # noqa: ANN001
        stmt = select(func.count()).select_from(model).where(model.user_id == user_id)
        if extra is not None:
            stmt = stmt.where(extra)
        result = await session.execute(stmt)
        return int(result.scalar_one() or 0)

    states = await count(JobUserState)
    filtered = await count(JobUserState, JobUserState.filter_passed.is_(False))
    analyzed = await count(JobAnalysis)
    drafts = await count(ResponseDraft)
    notified = await count(NotificationEvent, NotificationEvent.status == "sent")
    applied = await count(
        JobUserState, JobUserState.status.in_(["applied_manually", "sent_via_authorized_api"])
    )
    won = await count(JobUserState, JobUserState.status == "won")
    outreach = await count(OutreachEvent)
    return {
        "seen": states,
        "filtered_out": filtered,
        "analyzed": analyzed,
        "drafts": drafts,
        "notified": notified,
        "applied": applied,
        "won": won,
        "outreach_events": outreach,
    }
