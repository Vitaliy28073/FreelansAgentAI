from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.bot.handlers import setup_routers
from app.bot.middlewares.access import AllowlistMiddleware
from app.bot.notifier import TelegramNotifier
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.session import dispose_engine, init_db
from app.llm.factory import build_llm_provider
from app.scheduler.jobs import poll_all_sources
from app.services.analysis_service import AnalysisService
from app.services.ingestion import IngestionService

logger = get_logger("main")


async def _build_ingestion(bot: Bot) -> IngestionService:
    settings = get_settings()
    notifier = TelegramNotifier(bot)
    provider = build_llm_provider(settings) if settings.llm_configured else None
    analysis = AnalysisService(provider)

    async def notify(user, job, analysis_result, text: str | None = None) -> int | None:
        if text:
            await notifier.send_status(user, text)
            return None
        if job is None or analysis_result is None:
            return None
        return await notifier.send_job(user, job, analysis_result)

    return IngestionService(settings, analysis, notify)


async def run_bot() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")

    await init_db()
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.update.outer_middleware(AllowlistMiddleware(settings))
    dp.include_router(setup_routers())

    ingestion = await _build_ingestion(bot)
    scheduler = AsyncIOScheduler(timezone=settings.tz)

    async def poll_fl() -> None:
        await poll_all_sources(settings, ingestion)

    scheduler.add_job(
        poll_fl,
        "interval",
        seconds=settings.fl_rss_poll_seconds,
        id="poll_sources",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "bot_starting",
        fl_enabled=settings.fl_rss_enabled,
        fh_enabled=settings.freelancehunt_enabled,
        llm=settings.llm_configured,
    )
    try:
        await poll_fl()
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await dispose_engine()


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
