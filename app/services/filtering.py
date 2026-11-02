from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from app.db.models import FreelancerProfile, JobUserState
from app.domain.models import FilterResult, NormalizedJob

_WORD_RE = re.compile(r"[^\w+.#-]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return {part.lower() for part in _WORD_RE.split(text.lower()) if len(part) >= 2}


def _contains(haystack: str, needle: str) -> bool:
    return needle.lower() in haystack.lower()


def quick_filter(
    job: NormalizedJob,
    profile: FreelancerProfile | None,
    *,
    previous_state: JobUserState | None = None,
    now: datetime | None = None,
) -> FilterResult:
    reasons: list[str] = []
    matched: list[str] = []
    now = now or datetime.now(timezone.utc)
    blob = f"{job.title}\n{job.description}\n{job.category or ''}"

    if previous_state and previous_state.status in {"rejected", "skipped", "filtered_out"}:
        return FilterResult(passed=False, reasons=["already_rejected"])

    if not job.title.strip() or not job.canonical_url:
        return FilterResult(passed=False, reasons=["missing_required_fields"])

    if job.published_at and job.published_at < now - timedelta(days=14):
        return FilterResult(passed=False, reasons=["stale_listing"])

    if profile is None:
        return FilterResult(passed=True, reasons=["no_profile_yet"], matched_keywords=[])

    for stop in profile.stop_words or []:
        if stop and _contains(blob, stop):
            return FilterResult(passed=False, reasons=[f"stop_word:{stop}"])

    for category in profile.excluded_categories or []:
        if category and job.category and _contains(job.category, category):
            return FilterResult(passed=False, reasons=[f"excluded_category:{category}"])

    if (
        profile.min_budget is not None
        and job.budget.amount is not None
        and job.budget.amount < profile.min_budget
    ):
        return FilterResult(
            passed=False,
            reasons=[f"budget_below_min:{job.budget.amount}<{profile.min_budget}"],
        )

    required = [item for item in (profile.skills or []) if item]
    if required:
        job_tokens = _tokens(blob) | {skill.lower() for skill in job.skills}
        missing = [skill for skill in required if skill.lower() not in job_tokens and not _contains(blob, skill)]
        # Skills are preferred, not hard-required: keep as a soft signal unless none match at all
        # and the user also set keywords. Hard fail only on forbidden skills already handled.
        if missing and not any(_contains(blob, skill) for skill in required):
            # still pass if keywords match; otherwise keep for AI if keywords empty
            pass

    keywords = [item for item in (profile.keywords or []) if item]
    if keywords:
        hits = [word for word in keywords if _contains(blob, word)]
        if not hits:
            return FilterResult(passed=False, reasons=["no_keyword_match"])
        matched.extend(hits)
        reasons.append("keyword_match")
    else:
        reasons.append("no_keywords_configured")

    return FilterResult(passed=True, reasons=reasons or ["passed_default"], matched_keywords=matched)
