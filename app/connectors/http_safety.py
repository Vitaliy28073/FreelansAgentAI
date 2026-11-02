from __future__ import annotations

import asyncio
import random
import re
from typing import Any

import httpx

from app.core.exceptions import (
    AuthRequiredError,
    ChallengeDetectedError,
    ForbiddenError,
    RateLimitedError,
    SourceUnavailableError,
)

CHALLENGE_MARKERS = (
    "captcha",
    "recaptcha",
    "hcaptcha",
    "cf-challenge",
    "attention required",
    "access denied",
    "just a moment",
)


def looks_like_challenge(text: str, content_type: str | None = None) -> bool:
    lowered = text[:4000].lower()
    if content_type and "html" in content_type.lower() and any(
        marker in lowered for marker in CHALLENGE_MARKERS
    ):
        return True
    return any(marker in lowered for marker in ("g-recaptcha", "h-captcha", "cf-browser-verification"))


def retry_after_seconds(response: httpx.Response) -> float | None:
    header = response.headers.get("Retry-After")
    if not header:
        return None
    try:
        return float(header)
    except ValueError:
        return None


def classify_response(response: httpx.Response) -> None:
    status = response.status_code
    body = response.text[:2000]
    if looks_like_challenge(body, response.headers.get("content-type")):
        raise ChallengeDetectedError("Source returned an anti-bot challenge")
    if status == 401:
        raise AuthRequiredError("Source requires authentication")
    if status == 403:
        raise ForbiddenError("Source forbade access")
    if status == 429:
        raise RateLimitedError("Source rate-limited the request", retry_after=retry_after_seconds(response))
    if status >= 500:
        raise SourceUnavailableError(f"Source returned HTTP {status}")
    if status >= 400:
        raise SourceUnavailableError(f"Source returned HTTP {status}")


async def request_with_backoff(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int = 2,
    **kwargs: Any,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = await client.request(method, url, **kwargs)
            if response.status_code in {500, 502, 503, 504} and attempt < max_retries:
                delay = (2**attempt) + random.random()
                await asyncio.sleep(delay)
                continue
            classify_response(response)
            return response
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_error = exc
            if attempt >= max_retries:
                raise SourceUnavailableError("Network timeout talking to source") from exc
            await asyncio.sleep((2**attempt) + random.random())
        except RateLimitedError as exc:
            if attempt >= max_retries:
                raise
            await asyncio.sleep(exc.retry_after or ((2**attempt) + random.random()))
            last_error = exc
    raise SourceUnavailableError("Source unavailable") from last_error


_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(value: str) -> str:
    text = _TAG_RE.sub(" ", value)
    return re.sub(r"\s+", " ", text).strip()
