from aiogram import Router

from app.bot.handlers.callbacks import router as callbacks_router
from app.bot.handlers.commands import router as commands_router
from app.bot.handlers.profile import router as profile_router


def setup_routers() -> Router:
    root = Router()
    root.include_router(commands_router)
    root.include_router(profile_router)
    root.include_router(callbacks_router)
    return root
