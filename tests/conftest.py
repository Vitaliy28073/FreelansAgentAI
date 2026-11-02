from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Base

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    db = tmp_path / "test.db"
    return Settings(
        telegram_bot_token="test-token",
        allowed_telegram_user_ids="1",
        database_url=f"sqlite+aiosqlite:///{db}",
        fl_rss_enabled=True,
        freelancehunt_enabled=False,
        user_llm_api_key="",
        fl_rss_poll_seconds=120,
    )


@pytest.fixture
async def session(settings: Settings) -> AsyncSession:
    engine = create_async_engine(settings.database_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        yield db
    await engine.dispose()


@pytest.fixture
def fl_rss_xml() -> str:
    return (FIXTURES / "fl_rss.xml").read_text(encoding="utf-8")


@pytest.fixture
def fh_payload() -> dict:
    return json.loads((FIXTURES / "freelancehunt_projects.json").read_text(encoding="utf-8"))
