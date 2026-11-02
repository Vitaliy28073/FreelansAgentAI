from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ProfileStates(StatesGroup):
    specialization = State()
    skills = State()
    keywords = State()
    stop_words = State()
    min_budget = State()
    tone = State()
    portfolio = State()
