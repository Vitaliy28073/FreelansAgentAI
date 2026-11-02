from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.states.profile import ProfileStates
from app.db.repositories.users import get_or_create_user
from app.db.session import session_scope

router = Router()


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]


@router.message(Command("edit_profile"))
async def start_edit(message: Message, state: FSMContext) -> None:
    await state.set_state(ProfileStates.specialization)
    await message.answer("Специализация одной строкой. Например: Python / FastAPI / боты")


@router.message(ProfileStates.specialization)
async def set_specialization(message: Message, state: FSMContext) -> None:
    await state.update_data(specialization=(message.text or "").strip())
    await state.set_state(ProfileStates.skills)
    await message.answer("Навыки через запятую. Только то, что реально умеете.")


@router.message(ProfileStates.skills)
async def set_skills(message: Message, state: FSMContext) -> None:
    await state.update_data(skills=_split_list(message.text or ""))
    await state.set_state(ProfileStates.keywords)
    await message.answer("Ключевые слова для быстрого фильтра через запятую.")


@router.message(ProfileStates.keywords)
async def set_keywords(message: Message, state: FSMContext) -> None:
    await state.update_data(keywords=_split_list(message.text or ""))
    await state.set_state(ProfileStates.stop_words)
    await message.answer("Стоп-слова через запятую. Или «нет».")


@router.message(ProfileStates.stop_words)
async def set_stop_words(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    stops = [] if text.lower() in {"нет", "-", "no"} else _split_list(text)
    await state.update_data(stop_words=stops)
    await state.set_state(ProfileStates.min_budget)
    await message.answer("Минимальный бюджет числом в вашей валюте. Или «нет».")


@router.message(ProfileStates.min_budget)
async def set_min_budget(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip().replace(" ", "")
    value = None
    if text.lower() not in {"нет", "-", "no"}:
        try:
            value = float(text.replace(",", "."))
        except ValueError:
            await message.answer("Нужно число или «нет».")
            return
    await state.update_data(min_budget=value)
    await state.set_state(ProfileStates.tone)
    await message.answer("Тон отклика: professional / friendly / concise")


@router.message(ProfileStates.tone)
async def set_tone(message: Message, state: FSMContext) -> None:
    tone = (message.text or "professional").strip().lower()
    if tone not in {"professional", "friendly", "concise"}:
        tone = "professional"
    await state.update_data(tone=tone)
    await state.set_state(ProfileStates.portfolio)
    await message.answer(
        "Кейсы портфолио: каждый с новой строки в формате Название — стек — результат. "
        "Только подтверждённые работы. Или «нет»."
    )


@router.message(ProfileStates.portfolio)
async def set_portfolio(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    cases: list[dict[str, str]] = []
    if text.lower() not in {"нет", "-", "no"}:
        for line in text.splitlines():
            if line.strip():
                cases.append({"title": line.strip()})
    data = await state.get_data()
    async with session_scope() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        profile = user.profile
        profile.specialization = data.get("specialization") or ""
        profile.skills = data.get("skills") or []
        profile.keywords = data.get("keywords") or []
        profile.stop_words = data.get("stop_words") or []
        profile.min_budget = data.get("min_budget")
        profile.tone = data.get("tone") or "professional"
        profile.portfolio = cases
    await state.clear()
    await message.answer("Профиль сохранён. Новые заказы будут фильтроваться по этим данным.")


@router.message(F.text.startswith("/set_"))
async def unknown_set(message: Message) -> None:
    await message.answer("Используйте /edit_profile для последовательного заполнения.")
