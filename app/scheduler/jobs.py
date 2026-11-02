from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.connectors.registry import build_connectors
from app.core.config import Settings
from app.core.logging import get_logger
from app.db.repositories.connectors import get_or_create_connector
from app.db.repositories.users import list_active_users
from app.db.session import session_scope
from app.domain.enums import SourceCode
from app.services.ingestion import IngestionService

logger = get_logger("scheduler")

NotifyFn = Callable[..., Awaitable[int | None]]


async def poll_all_sources(settings: Settings, ingestion: IngestionService) -> None:
    connectors = build_connectors(settings)
    if not connectors:
        logger.warning("no_connectors_enabled")
        return
    async with session_scope() as session:
        users = await list_active_users(session)
        for user in users:
            if user.paused:
                continue
            for code, connector in connectors.items():
                enabled = (
                    settings.fl_rss_enabled
                    if code is SourceCode.FL_RSS
                    else settings.freelancehunt_enabled and bool(settings.freelancehunt_token)
                )
                source_row = await get_or_create_connector(
                    session,
                    user.id,
                    code.value,
                    enabled=enabled,
                    access_method=connector.access_method,
                )
                source_row.enabled = enabled
                try:
                    await ingestion.run_connector(
                        session,
                        connector=connector,
                        user=user,
                        source_row=source_row,
                        profile=user.profile,
                    )
                except Exception:
                    logger.exception("poll_failed", source=code.value, user_id=user.id)
        for connector in connectors.values():
            await connector.close()
