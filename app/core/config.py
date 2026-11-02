from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = ""
    allowed_telegram_user_ids: str = ""

    database_url: str = "sqlite+aiosqlite:///./data/radar.db"

    user_llm_api_key: str = ""
    user_llm_base_url: str = "https://api.deepseek.com/v1"
    user_llm_model: str = "deepseek-chat"
    llm_provider: str = "openai_compatible"
    llm_timeout_seconds: float = 45.0
    llm_max_retries: int = 1

    freelancehunt_token: str = ""
    freelancehunt_enabled: bool = False
    freelancehunt_poll_seconds: int = 180
    freelancehunt_base_url: str = "https://api.freelancehunt.com/v2"

    fl_rss_url: str = "https://www.fl.ru/rss/all.xml"
    fl_rss_enabled: bool = True
    fl_rss_poll_seconds: int = 300

    max_jobs_per_poll: int = 40
    max_notifications_per_day: int = 30
    notify_score_threshold: int = 45
    full_monitoring: bool = False

    encryption_key: str = ""
    log_level: str = "INFO"
    tz: str = "UTC"
    http_timeout_seconds: float = 20.0
    http_max_retries: int = 2

    @field_validator("fl_rss_poll_seconds")
    @classmethod
    def min_fl_interval(cls, value: int) -> int:
        return max(value, 120)

    @field_validator("freelancehunt_poll_seconds")
    @classmethod
    def min_fh_interval(cls, value: int) -> int:
        return max(value, 60)

    @property
    def allowed_ids(self) -> set[int]:
        if not self.allowed_telegram_user_ids.strip():
            return set()
        return {
            int(item.strip())
            for item in self.allowed_telegram_user_ids.split(",")
            if item.strip()
        }

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def llm_configured(self) -> bool:
        return bool(self.user_llm_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_sqlite:
        path = settings.database_url.split("///")[-1]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return settings
