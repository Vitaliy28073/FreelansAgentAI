from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConnectorRun, SourceConnector, SourceCredential


async def get_or_create_connector(
    session: AsyncSession,
    user_id: int,
    code: str,
    *,
    enabled: bool,
    access_method: str,
) -> SourceConnector:
    result = await session.execute(
        select(SourceConnector).where(
            SourceConnector.user_id == user_id, SourceConnector.code == code
        )
    )
    connector = result.scalar_one_or_none()
    if connector:
        return connector
    connector = SourceConnector(
        user_id=user_id,
        code=code,
        enabled=enabled,
        status="enabled" if enabled else "disabled",
        access_method=access_method,
        rules_checked_at=datetime.now(timezone.utc),
    )
    session.add(connector)
    await session.flush()
    return connector


async def list_connectors(session: AsyncSession, user_id: int) -> list[SourceConnector]:
    result = await session.execute(
        select(SourceConnector).where(SourceConnector.user_id == user_id)
    )
    return list(result.scalars().all())


async def save_cursor(session: AsyncSession, connector: SourceConnector, cursor: dict[str, Any]) -> None:
    connector.cursor = cursor
    connector.last_success_at = datetime.now(timezone.utc)
    connector.last_error = None
    connector.last_error_code = None
    connector.consecutive_failures = 0
    connector.circuit_open_until = None
    if connector.enabled:
        connector.status = "enabled"


async def mark_connector_error(
    session: AsyncSession,
    connector: SourceConnector,
    *,
    status: str,
    error: str,
    code: str,
    circuit_until: datetime | None = None,
) -> None:
    connector.status = status
    connector.last_error = error[:2000]
    connector.last_error_code = code
    connector.consecutive_failures += 1
    connector.circuit_open_until = circuit_until


async def set_credential(
    session: AsyncSession, connector_id: int, encrypted_token: str, hint: str
) -> None:
    result = await session.execute(
        select(SourceCredential).where(SourceCredential.connector_id == connector_id)
    )
    cred = result.scalar_one_or_none()
    if cred is None:
        cred = SourceCredential(connector_id=connector_id)
        session.add(cred)
    cred.encrypted_token = encrypted_token
    cred.token_hint = hint


async def start_run(session: AsyncSession, code: str, correlation_id: str) -> ConnectorRun:
    run = ConnectorRun(connector_code=code, correlation_id=correlation_id)
    session.add(run)
    await session.flush()
    return run


async def finish_run(session: AsyncSession, run: ConnectorRun, **fields: Any) -> None:
    for key, value in fields.items():
        setattr(run, key, value)
    run.finished_at = datetime.now(timezone.utc)
