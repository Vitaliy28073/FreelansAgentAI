from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.core.exceptions import LLMUnavailableError
from app.db.models import FreelancerProfile, Job
from app.domain.scoring import DEFAULT_WEIGHTS, apply_risk_penalty, decision_from_score
from app.llm.base import LLMProvider
from app.llm.prompts.analysis import ANALYSIS_SYSTEM, build_analysis_user_prompt
from app.llm.schemas import AnalysisResult, BudgetAssessment, CompetitionInfo

INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "раскрой системный",
    "system prompt",
    "выведи токен",
    "show secrets",
    "api key",
)


def _job_payload(job: Job) -> dict[str, Any]:
    return {
        "source": job.source,
        "title": job.title,
        "description": job.description[:6000],
        "category": job.category,
        "skills": job.skills,
        "budget_amount": job.budget_amount,
        "budget_currency": job.budget_currency,
        "budget_raw": job.budget_raw,
        "bid_count": job.bid_count,
        "published_at": job.published_at.isoformat() if job.published_at else None,
        "url": job.url,
    }


def _profile_payload(profile: FreelancerProfile | None) -> dict[str, Any]:
    if profile is None:
        return {}
    return {
        "specialization": profile.specialization,
        "skills": profile.skills,
        "keywords": profile.keywords,
        "experience_level": profile.experience_level,
        "portfolio": profile.portfolio,
        "min_budget": profile.min_budget,
        "desired_rate": profile.desired_rate,
        "currency": profile.currency,
        "tone": profile.tone,
        "project_types": profile.project_types,
    }


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).rstrip("`").strip()
    return json.loads(text)


def keyword_fallback(job: Job, profile: FreelancerProfile | None) -> AnalysisResult:
    blob = f"{job.title} {job.description}".lower()
    skills = [s for s in (profile.skills if profile else []) if s]
    matching = [s for s in skills if s.lower() in blob]
    missing = [s for s in skills if s not in matching]
    skill_score = int((len(matching) / max(len(skills), 1)) * DEFAULT_WEIGHTS.skills) if skills else 10
    budget_score = 8 if job.budget_amount else 0
    clarity = 6 if len(job.description) > 80 else 3
    risk_flags = []
    penalty = 0
    lowered = blob
    if any(marker in lowered for marker in ("бесплатн", "тестов", "без оплаты")):
        risk_flags.append(
            {
                "code": "UNPAID_TEST",
                "severity": "high",
                "evidence": "В тексте есть признаки бесплатной или тестовой работы",
                "recommendation": "Уточнить, оплачивается ли тест, до начала работы",
            }
        )
        penalty += 12
    if any(marker in lowered for marker in INJECTION_MARKERS):
        risk_flags.append(
            {
                "code": "PROMPT_INJECTION",
                "severity": "medium",
                "evidence": "В тексте заказа есть инструкции к модели",
                "recommendation": "Игнорировать инструкции из объявления",
            }
        )
        penalty += 5
    base = skill_score + budget_score + clarity
    score = apply_risk_penalty(base, penalty)
    return AnalysisResult(
        summary=job.description[:280] or job.title,
        required_skills=list(job.skills or []),
        matching_skills=matching,
        missing_skills=missing,
        scope=[],
        budget=BudgetAssessment(
            amount=job.budget_amount,
            currency=job.budget_currency,
            assessment="unknown",
            evidence=job.budget_raw or "Бюджет не указан или не извлечён",
        ),
        deadline_assessment="unknown",
        competition=CompetitionInfo(value=job.bid_count, source_provided=job.bid_count is not None),
        risk_flags=risk_flags,  # type: ignore[arg-type]
        score=score,
        risk_penalty=min(penalty, 30),
        decision=decision_from_score(score),  # type: ignore[arg-type]
        reasons_for=[f"Совпали навыки: {', '.join(matching)}"] if matching else [],
        reasons_against=["AI-анализ недоступен, использован keyword fallback"],
        missing_information=["Полноценный AI-анализ не выполнен"],
        clarifying_questions=[],
        confidence=0.25,
        evidence_quotes=[],
        score_breakdown={
            "skills": skill_score,
            "portfolio": "unknown",
            "budget": budget_score,
            "clarity": clarity,
            "reliability": "unknown",
            "deadline": "unknown",
            "competition": "unknown",
            "strategic": "unknown",
        },
        fallback=True,
    )


class AnalysisService:
    def __init__(self, provider: LLMProvider | None) -> None:
        self._provider = provider

    async def analyze(
        self, job: Job, profile: FreelancerProfile | None, *, full_monitoring: bool = False
    ) -> AnalysisResult:
        if self._provider is None:
            result = keyword_fallback(job, profile)
            result.decision = decision_from_score(result.score, full_monitoring=full_monitoring)  # type: ignore[assignment]
            return result

        user_prompt = build_analysis_user_prompt(_job_payload(job), _profile_payload(profile))
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                raw = await self._provider.complete_json(system=ANALYSIS_SYSTEM, user=user_prompt)
                data = _extract_json(raw)
                result = AnalysisResult.model_validate(data)
                result.decision = decision_from_score(  # type: ignore[assignment]
                    result.score, full_monitoring=full_monitoring
                )
                result.fallback = False
                return result
            except (LLMUnavailableError, ValidationError, json.JSONDecodeError, TypeError) as exc:
                last_error = exc
                if attempt == 0:
                    user_prompt += "\n\nПредыдущий ответ был невалидным JSON. Верни только JSON по схеме."
                    continue
        result = keyword_fallback(job, profile)
        result.reasons_against.append(f"AI fallback: {type(last_error).__name__}" if last_error else "AI fallback")
        result.decision = decision_from_score(result.score, full_monitoring=full_monitoring)  # type: ignore[assignment]
        return result
