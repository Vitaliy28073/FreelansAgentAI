from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.db.models import Job


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/latest"), KeyboardButton(text="/profile")],
            [KeyboardButton(text="/filters"), KeyboardButton(text="/sources")],
            [KeyboardButton(text="/stats"), KeyboardButton(text="/help")],
        ],
        resize_keyboard=True,
    )


def job_keyboard(job: Job, *, has_drafts: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Открыть заказ", url=job.url)],
        [
            InlineKeyboardButton(text="Сгенерировать отклик", callback_data=f"draft:{job.id}"),
            InlineKeyboardButton(text="Другой вариант", callback_data=f"redraft:{job.id}"),
        ],
        [
            InlineKeyboardButton(text="Скопировать отклик", callback_data=f"copy:{job.id}"),
            InlineKeyboardButton(text="Уточняющий вопрос", callback_data=f"question:{job.id}"),
        ],
        [
            InlineKeyboardButton(text="В избранное", callback_data=f"fav:{job.id}"),
            InlineKeyboardButton(text="Не подходит", callback_data=f"skip:{job.id}"),
        ],
        [
            InlineKeyboardButton(text="Откликнулся вручную", callback_data=f"applied:{job.id}"),
            InlineKeyboardButton(text="Пауза по источнику", callback_data=f"pause_src:{job.source}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def copy_keyboard(job_id: int, styles: list[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Показать {style}", callback_data=f"showdraft:{job_id}:{style}")]
            for style in styles
        ]
    )


def confirm_delete_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, удалить мои данные", callback_data="delete_yes"),
                InlineKeyboardButton(text="Отмена", callback_data="delete_no"),
            ]
        ]
    )
