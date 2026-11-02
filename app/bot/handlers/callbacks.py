from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.formatting import drafts_message
from app.bot.keyboards.common import copy_keyboard
from app.core.config import get_settings
from app.db.models import OutreachEvent
from app.db.repositories.connectors import list_connectors
from app.db.repositories.jobs import (
    get_job,
    get_or_create_user_state,
    latest_analysis,
    list_drafts,
    save_drafts,
)
from app.db.repositories.users import delete_user_data, get_or_create_user
from app.db.session import session_scope
from app.llm.factory import build_llm_provider
from app.llm.schemas import AnalysisResult
from app.services.response_generator import ResponseGenerator

router = Router()


def _generator() -> ResponseGenerator:
    settings = get_settings()
    provider = build_llm_provider(settings) if settings.llm_configured else None
    return ResponseGenerator(provider)


@router.callback_query(F.data.startswith("draft:") | F.data.startswith("redraft:"))
async def cb_draft(callback: CallbackQuery) -> None:
    _, job_id_s = callback.data.split(":", 1)
    job_id = int(job_id_s)
    async with session_scope() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        job = await get_job(session, job_id)
        if job is None:
            await callback.answer("Заказ не найден", show_alert=True)
            return
        analysis_row = await latest_analysis(session, job.id, user.id)
        analysis = (
            AnalysisResult.model_validate(analysis_row.result)
            if analysis_row
            else AnalysisResult(summary=job.description[:280], fallback=True)
        )
        bundle = await _generator().generate(job, analysis, user.profile)
        await save_drafts(
            session,
            job.id,
            user.id,
            [item.model_dump() for item in bundle.variants],
        )
        state = await get_or_create_user_state(session, user.id, job.id)
        state.status = "draft_ready"
        session.add(OutreachEvent(user_id=user.id, job_id=job.id, action="draft_generated"))
        text = drafts_message(bundle)
    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=copy_keyboard(job_id, ["short", "standard", "technical"]),
    )
    await callback.answer("Черновики готовы")


@router.callback_query(F.data.startswith("copy:") | F.data.startswith("showdraft:"))
async def cb_copy(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    job_id = int(parts[1])
    style = parts[2] if len(parts) > 2 else "standard"
    async with session_scope() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        drafts = await list_drafts(session, job_id, user.id)
        if not drafts:
            await callback.answer("Сначала сгенерируйте отклик", show_alert=True)
            return
        chosen = next((item for item in drafts if item.style == style), drafts[0])
        session.add(
            OutreachEvent(
                user_id=user.id,
                job_id=job_id,
                action="copied_draft",
                payload={"style": chosen.style},
            )
        )
        body = chosen.edited_body or chosen.body
    await callback.message.answer(
        f"Скопируйте текст и вставьте на площадке. Бот ничего не отправляет.\n\n{body}"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("question:"))
async def cb_question(callback: CallbackQuery) -> None:
    job_id = int(callback.data.split(":")[1])
    async with session_scope() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        analysis = await latest_analysis(session, job_id, user.id)
        questions = (analysis.result or {}).get("clarifying_questions") if analysis else []
        missing = (analysis.result or {}).get("missing_information") if analysis else []
        items = questions or missing or ["Какой ожидаемый результат и критерий приёмки?"]
        text = "Уточняющий вопрос, который можно задать на площадке:\n\n" + items[0]
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data.startswith("fav:"))
async def cb_fav(callback: CallbackQuery) -> None:
    job_id = int(callback.data.split(":")[1])
    async with session_scope() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        job = await get_job(session, job_id)
        if job is None:
            await callback.answer("Заказ не найден", show_alert=True)
            return
        state = await get_or_create_user_state(session, user.id, job.id)
        state.favorite = True
        state.status = "shortlisted"
    await callback.answer("В избранном")


@router.callback_query(F.data.startswith("skip:"))
async def cb_skip(callback: CallbackQuery) -> None:
    job_id = int(callback.data.split(":")[1])
    async with session_scope() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        job = await get_job(session, job_id)
        if job is None:
            await callback.answer("Заказ не найден", show_alert=True)
            return
        state = await get_or_create_user_state(session, user.id, job.id)
        state.status = "rejected"
        session.add(
            OutreachEvent(user_id=user.id, job_id=job.id, action="rejected", payload={})
        )
    await callback.answer("Скрыто")


@router.callback_query(F.data.startswith("applied:"))
async def cb_applied(callback: CallbackQuery) -> None:
    job_id = int(callback.data.split(":")[1])
    async with session_scope() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        job = await get_job(session, job_id)
        if job is None:
            await callback.answer("Заказ не найден", show_alert=True)
            return
        state = await get_or_create_user_state(session, user.id, job.id)
        state.status = "applied_manually"
        session.add(
            OutreachEvent(user_id=user.id, job_id=job.id, action="applied_manually")
        )
    await callback.answer("Отметил ручной отклик")


@router.callback_query(F.data.startswith("pause_src:"))
async def cb_pause_src(callback: CallbackQuery) -> None:
    code = callback.data.split(":", 1)[1]
    async with session_scope() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        rows = await list_connectors(session, user.id)
        found = False
        for row in rows:
            if row.code == code:
                row.enabled = False
                row.status = "paused"
                found = True
        if not found:
            await callback.answer("Источник не найден", show_alert=True)
            return
    await callback.answer(f"{code} на паузе")
    await callback.message.answer(
        f"Источник {code} поставлен на паузу. Возобновить: /resume и /sources."
    )


@router.callback_query(F.data == "delete_yes")
async def cb_delete_yes(callback: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        await delete_user_data(session, user)
    await callback.message.answer("Данные удалены.")
    await callback.answer()


@router.callback_query(F.data == "delete_no")
async def cb_delete_no(callback: CallbackQuery) -> None:
    await callback.answer("Отменено")
