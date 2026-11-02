from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import BaseConnector
from app.connectors.cursor import cursor_is_bootstrapped
from app.core.config import Settings
from app.core.exceptions import (
    AuthRequiredError,
    ChallengeDetectedError,
    ConnectorError,
    ForbiddenError,
    RateLimitedError,
    SchemaChangedError,
    SourceUnavailableError,
)
from app.core.logging import get_logger
from app.core.security import new_correlation_id
from app.db.models import ConnectorRun, FreelancerProfile, NotificationEvent, User
from app.db.repositories.connectors import finish_run, mark_connector_error, save_cursor, start_run
from app.db.repositories.jobs import (
    count_today_notifications,
    get_or_create_user_state,
    save_analysis,
)
from app.domain.enums import ConnectorStatus, SourceCode
from app.services.analysis_service import AnalysisService
from app.services.deduplication import persist_if_new
from app.services.filtering import quick_filter

logger = get_logger("ingestion")

STATUS_MAP = {
    "AUTH_REQUIRED": ConnectorStatus.AUTH_REQUIRED.value,
    "FORBIDDEN": ConnectorStatus.FORBIDDEN.value,
    "RATE_LIMITED": ConnectorStatus.RATE_LIMITED.value,
    "CHALLENGE_DETECTED": ConnectorStatus.CHALLENGE.value,
    "SOURCE_UNAVAILABLE": ConnectorStatus.UNAVAILABLE.value,
    "SCHEMA_CHANGED": ConnectorStatus.MANUAL_REVIEW.value,
}


class IngestionService:
    def __init__(
        self,
        settings: Settings,
        analysis: AnalysisService,
        notify,
    ) -> None:
        self._settings = settings
        self._analysis = analysis
        self._notify = notify

    async def run_connector(
        self,
        session: AsyncSession,
        *,
        connector: BaseConnector,
        user: User,
        source_row,
        profile: FreelancerProfile | None,
    ) -> ConnectorRun:
        correlation_id = new_correlation_id()
        run = await start_run(session, connector.code.value, correlation_id)
        log = logger.bind(source=connector.code.value, run_id=run.id, cid=correlation_id)

        if user.paused or not source_row.enabled:
            await finish_run(session, run, error="paused_or_disabled")
            return run
        if source_row.circuit_open_until and source_row.circuit_open_until > datetime.now(timezone.utc):
            await finish_run(session, run, error="circuit_open")
            return run
        if source_row.status in {
            ConnectorStatus.FORBIDDEN.value,
            ConnectorStatus.CHALLENGE.value,
            ConnectorStatus.AUTH_REQUIRED.value,
            ConnectorStatus.MANUAL_REVIEW.value,
        }:
            await finish_run(session, run, error=f"blocked:{source_row.status}")
            return run

        fetched = inserted = duplicates = filtered = analyzed = notified = 0
        try:
            previous_cursor = source_row.cursor or {}
            was_bootstrapped = cursor_is_bootstrapped(previous_cursor)
            raw_jobs, cursor = await connector.fetch_new_jobs(
                previous_cursor, self._settings.max_jobs_per_poll
            )
            fetched = len(raw_jobs)
            if not was_bootstrapped:
                snapshot = len((cursor or {}).get("seen_ids") or [])
                await save_cursor(session, source_row, cursor)
                await finish_run(session, run, fetched=snapshot, inserted=0)
                log.info("connector_bootstrapped", seen=snapshot)
                await self._notify_bootstrap(user, connector.code, cursor)
                return run

            daily_cap = user.max_notifications_per_day or self._settings.max_notifications_per_day
            already_sent = await count_today_notifications(session, user.id)

            for raw in raw_jobs:
                normalized = connector.normalize(raw)
                job, created = await persist_if_new(session, normalized)
                if not created:
                    duplicates += 1
                    continue
                inserted += 1

                state = await get_or_create_user_state(session, user.id, job.id)
                filt = quick_filter(normalized, profile, previous_state=state)
                state.filter_passed = filt.passed
                state.filter_reasons = filt.reasons + [
                    f"matched:{item}" for item in filt.matched_keywords
                ]
                if not filt.passed:
                    state.status = "filtered_out"
                    filtered += 1
                    continue

                analysis = await self._analysis.analyze(
                    job, profile, full_monitoring=user.full_monitoring
                )
                await save_analysis(
                    session,
                    job_id=job.id,
                    user_id=user.id,
                    provider=self._analysis._provider.name if self._analysis._provider else "fallback",
                    model=self._analysis._provider.model if self._analysis._provider else "keyword",
                    result=analysis.model_dump(),
                    score=analysis.score,
                    risk_penalty=analysis.risk_penalty,
                    decision=analysis.decision,
                    confidence=analysis.confidence,
                    summary=analysis.summary,
                    fallback=analysis.fallback,
                )
                analyzed += 1
                job.status = "analyzed"
                state.status = "analyzed"

                threshold = user.notify_score_threshold or self._settings.notify_score_threshold
                should_notify = analysis.decision != "skip" and analysis.score >= threshold
                if user.full_monitoring:
                    should_notify = True
                if already_sent + notified >= daily_cap:
                    should_notify = False
                if state.notified_at is not None:
                    should_notify = False
                if should_notify:
                    message_id = await self._notify(user, job, analysis)
                    state.notified_at = datetime.now(timezone.utc)
                    state.telegram_chat_id = user.telegram_id
                    state.telegram_message_id = message_id
                    session.add(
                        NotificationEvent(
                            user_id=user.id, job_id=job.id, channel="telegram", status="sent"
                        )
                    )
                    notified += 1

            await save_cursor(session, source_row, cursor)
            await finish_run(
                session,
                run,
                fetched=fetched,
                inserted=inserted,
                duplicates=duplicates,
                filtered=filtered,
                analyzed=analyzed,
                notified=notified,
            )
            log.info(
                "connector_run_ok",
                fetched=fetched,
                inserted=inserted,
                duplicates=duplicates,
                filtered=filtered,
                analyzed=analyzed,
                notified=notified,
            )
        except ConnectorError as exc:
            until = None
            if isinstance(exc, RateLimitedError):
                until = datetime.now(timezone.utc) + timedelta(seconds=exc.retry_after or 600)
            elif isinstance(exc, SourceUnavailableError):
                until = datetime.now(timezone.utc) + timedelta(minutes=15)
            status = STATUS_MAP.get(exc.code, ConnectorStatus.UNAVAILABLE.value)
            await mark_connector_error(
                session,
                source_row,
                status=status,
                error=str(exc),
                code=exc.code,
                circuit_until=until,
            )
            await finish_run(session, run, error=str(exc), error_code=exc.code, fetched=fetched)
            log.warning("connector_run_failed", code=exc.code, error=str(exc))
            if isinstance(exc, (ForbiddenError, ChallengeDetectedError, AuthRequiredError, SchemaChangedError)):
                await self._notify_owner_status(user, connector.code, exc)
        return run

    async def _notify_bootstrap(self, user: User, source: SourceCode, cursor: dict) -> None:
        seen = len((cursor or {}).get("seen_ids") or [])
        text = (
            f"Источник {source.value} инициализирован.\n"
            f"Текущая лента ({seen} заказов) сохранена как точка отсчёта.\n"
            "Дальше пришлю только новые заказы после фильтра и анализа."
        )
        try:
            await self._notify(user, None, None, text=text)
        except Exception:
            logger.warning("bootstrap_notify_failed", source=source.value)

    async def _notify_owner_status(self, user: User, source: SourceCode, exc: ConnectorError) -> None:
        text = (
            f"Источник {source.value} остановлен.\n"
            f"Код: {exc.code}\n"
            f"{exc}\n"
            "Обход защиты не выполняется. Проверьте доступ официальным способом."
        )
        try:
            await self._notify(user, None, None, text=text)
        except Exception:
            logger.warning("status_notify_failed", source=source.value)
