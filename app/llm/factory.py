from __future__ import annotations

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.providers.openai_compatible import OpenAICompatibleProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider in {"openai_compatible", "openai", "deepseek"}:
        return OpenAICompatibleProvider(settings)
    return OpenAICompatibleProvider(settings)
