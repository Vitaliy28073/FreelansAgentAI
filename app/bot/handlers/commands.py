from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.bot.formatting import job_card, profile_message
from app.bot.keyboards.common import confirm_delete_keyboard, job_keyboard, main_menu
from app.core.config import get_settings
from app.db.repositories.connectors import get_or_create_connector, list_connectors
from app.db.repositories.jobs import latest_analysis, list_recent_jobs
from app.db.repositories.users import get_or_create_user
from app.db.session import session_scope
from app.services.statistics import user_stats

router = Router()


HELP_TEXT = (
    "Freelance Radar AI — персональный ассистент по поиску заказов.\n\n"
    "Цепочка: источник → база → фильтр → AI-анализ → Telegram → черновик отклика.\n"
    "Бот не отправляет отклики на площадки автоматически.\n\n"
    "/start — регистрация\n"
    "/profile — профиль исполнителя\n"
    "/filters — ключевые слова, стоп-слова, бюджет\n"
    "/sources — источники и их статус\n"
    "/latest — последние подходящие заказы\n"
    "/favorites — избранное\n"
    "/history — история действий\n"
    "/stats — статистика\n"
    "/pause и /resume — глобальная пауза\n"
    "/status — здоровье коннекторов\n"
    "/settings — порог уведомлений\n"
    "/delete_me — удаление данных\n"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    settings = get_settings()
    async with session_scope() as session:
        user = await get_or_create_user(
            session, message.from_user.id, message.from_user.username
        )
        await get_or_create_connector(
            session,
            user.id,
            "fl_rss",
            enabled=settings.fl_rss_enabled,
            access_method="rss",
        )
        await get_or_create_connector(
            session,
            user.id,
            "freelancehunt",
            enabled=settings.freelancehunt_enabled and bool(settings.freelancehunt_token),
            access_method="api",
        )
    await message.answer(
        "Я персональный AI-ассистент по поиску клиентов.\n\n"
        "Сейчас разрешённые источники:\n"
        "- FL.ru публичный RSS\n"
        "- Freelancehunt API 2.0 (если задан токен)\n\n"
        "Я анализирую заказы и готовлю первый отклик. "
        "Отправку на площадку не делаю — копируете текст и открываете исходный заказ.\n\n"
        "Дальше заполните профиль: /profile\n"
        "Проверить источники: /sources",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        assert user.profile is not None
        await message.answer(
            profile_message(user.profile) + "\n\nРедактирование: отправьте /edit_profile",
            parse_mode="HTML",
        )


@router.message(Command("filters"))
async def cmd_filters(message: Message) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        profile = user.profile
        text = (
            "<b>Фильтры</b>\n"
            f"Ключевые слова: {', '.join(profile.keywords or []) or 'не заданы'}\n"
            f"Стоп-слова: {', '.join(profile.stop_words or []) or 'нет'}\n"
            f"Мин. бюджет: {profile.min_budget or 'не задан'}\n"
            f"Порог уведомления: {user.notify_score_threshold}\n"
            f"Лимит уведомлений/день: {user.max_notifications_per_day}\n"
            f"Полный мониторинг: {'да' if user.full_monitoring else 'нет'}\n\n"
            "Изменить: /edit_profile"
        )
        await message.answer(text, parse_mode="HTML")


@router.message(Command("sources"))
async def cmd_sources(message: Message) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        rows = await list_connectors(session, user.id)
        if not rows:
            await message.answer("Источники ещё не созданы. Нажмите /start.")
            return
        lines = ["<b>Источники</b>"]
        for row in rows:
            mark = "вкл" if row.enabled and row.status == "enabled" else row.status
            last = row.last_success_at.strftime("%Y-%m-%d %H:%M UTC") if row.last_success_at else "ещё не было"
            err = f"\nОшибка: {row.last_error_code}" if row.last_error_code else ""
            lines.append(
                f"\n<code>{row.code}</code> — {row.access_method}, {mark}\n"
                f"Последний успешный опрос: {last}{err}"
            )
        lines.append(
            "\nFL.ru: публичный RSS, отклик только вручную.\n"
            "Freelancehunt: официальный API 2.0. Токен задаётся в FREELANCEHUNT_TOKEN. "
            "Автоотправка bid выключена."
        )
        await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("latest"))
async def cmd_latest(message: Message) -> None:
    await _send_job_list(message, favorites=False)


@router.message(Command("favorites"))
async def cmd_favorites(message: Message) -> None:
    await _send_job_list(message, favorites=True)


async def _send_job_list(message: Message, *, favorites: bool) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        rows = await list_recent_jobs(session, user.id, limit=5, favorites=favorites)
        if not rows:
            await message.answer("Пока нет карточек. Дождитесь ближайшего опроса источников.")
            return
        for job, _state in rows:
            analysis = await latest_analysis(session, job.id, user.id)
            await message.answer(
                job_card(job, analysis),
                parse_mode="HTML",
                reply_markup=job_keyboard(job),
                disable_web_page_preview=True,
            )


@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        rows = await list_recent_jobs(session, user.id, limit=10)
        if not rows:
            await message.answer("История пуста.")
            return
        lines = ["<b>История</b>"]
        for job, state in rows:
            lines.append(f"{state.status} — {job.title[:80]}")
        await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        stats = await user_stats(session, user.id)
        text = (
            "<b>Статистика</b>\n"
            f"Просмотрено карточек: {stats['seen']}\n"
            f"Отфильтровано: {stats['filtered_out']}\n"
            f"AI-анализов: {stats['analyzed']}\n"
            f"Черновиков: {stats['drafts']}\n"
            f"Уведомлений: {stats['notified']}\n"
            f"Ручных откликов: {stats['applied']}\n"
            f"Выиграно: {stats['won']}"
        )
        await message.answer(text, parse_mode="HTML")


@router.message(Command("pause"))
async def cmd_pause(message: Message) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        user.paused = True
    await message.answer("Глобальная пауза включена. Источники не опрашиваются.")


@router.message(Command("resume"))
async def cmd_resume(message: Message) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        user.paused = False
    await message.answer("Мониторинг возобновлён.")


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    settings = get_settings()
    async with session_scope() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        rows = await list_connectors(session, user.id)
        llm = "настроен" if settings.llm_configured else "нет ключа, работает keyword fallback"
        lines = [
            "<b>Здоровье</b>",
            f"LLM: {llm}",
            f"Пауза пользователя: {'да' if user.paused else 'нет'}",
        ]
        for row in rows:
            lines.append(
                f"{row.code}: {row.status}, failures={row.consecutive_failures}"
            )
        await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        await message.answer(
            "Порог уведомлений и лимит задаются в профиле через /edit_profile.\n"
            f"Сейчас порог={user.notify_score_threshold}, лимит/день={user.max_notifications_per_day}, "
            f"full_monitoring={'on' if user.full_monitoring else 'off'}."
        )


@router.message(Command("delete_me"))
async def cmd_delete_me(message: Message) -> None:
    await message.answer(
        "Удалить профиль, историю анализов и черновики? Это необратимо.",
        reply_markup=confirm_delete_keyboard(),
    )
