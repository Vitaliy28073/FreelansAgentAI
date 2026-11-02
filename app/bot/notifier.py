from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ParseMode

from app.bot.formatting import job_card
from app.bot.keyboards.common import job_keyboard
from app.db.models import Job, User
from app.llm.schemas import AnalysisResult


class TelegramNotifier:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_job(self, user: User, job: Job, analysis: AnalysisResult) -> int:
        message = await self._bot.send_message(
            chat_id=user.telegram_id,
            text=job_card(job, analysis),
            parse_mode=ParseMode.HTML,
            reply_markup=job_keyboard(job),
            disable_web_page_preview=True,
        )
        return message.message_id

    async def send_status(self, user: User, text: str) -> None:
        await self._bot.send_message(chat_id=user.telegram_id, text=text)
