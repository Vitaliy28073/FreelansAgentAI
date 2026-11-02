from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.core.config import Settings


class AllowlistMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message) and event.from_user or isinstance(event, CallbackQuery) and event.from_user:
            user = event.from_user
        if user is None:
            return None
        allowed = self._settings.allowed_ids
        if allowed and user.id not in allowed:
            if isinstance(event, Message):
                await event.answer("Этот бот персональный. Ваш Telegram ID не в списке доступа.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Нет доступа", show_alert=True)
            return None
        return await handler(event, data)
