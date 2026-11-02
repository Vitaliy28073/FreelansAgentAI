from __future__ import annotations

import json

import httpx

from app.core.config import Settings
from app.core.exceptions import LLMUnavailableError
from app.llm.base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self.model = settings.user_llm_model
        self._client = client
        self._owns_client = client is None

    async def complete_json(self, *, system: str, user: str) -> str:
        if not self._settings.user_llm_api_key:
            raise LLMUnavailableError("LLM API key is not configured")
        client = self._client or httpx.AsyncClient(timeout=self._settings.llm_timeout_seconds)
        try:
            response = await client.post(
                f"{self._settings.user_llm_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._settings.user_llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._settings.user_llm_model,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
        except httpx.HTTPError as exc:
            raise LLMUnavailableError("LLM provider is unreachable") from exc
        finally:
            if self._owns_client and self._client is None:
                await client.aclose()

        if response.status_code >= 400:
            raise LLMUnavailableError(f"LLM provider returned HTTP {response.status_code}")
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
            raise LLMUnavailableError("LLM provider returned an unexpected payload") from exc
        if not content:
            raise LLMUnavailableError("LLM provider returned empty content")
        return content
