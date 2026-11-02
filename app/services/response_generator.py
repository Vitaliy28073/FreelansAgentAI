from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.core.exceptions import LLMUnavailableError
from app.db.models import FreelancerProfile, Job
from app.llm.base import LLMProvider
from app.llm.prompts.response import RESPONSE_SYSTEM, build_response_user_prompt
from app.llm.schemas import AnalysisResult, DraftBundle, DraftVariant


def _safe_profile(profile: FreelancerProfile | None) -> dict[str, Any]:
    if profile is None:
        return {"skills": [], "portfolio": [], "specialization": "", "tone": "professional"}
    return {
        "specialization": profile.specialization,
        "skills": profile.skills,
        "experience_level": profile.experience_level,
        "portfolio": profile.portfolio,
        "availability": profile.availability,
        "tone": profile.tone,
        "sample_responses": (profile.sample_responses or [])[:3],
        "languages": profile.languages,
    }


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).rstrip("`").strip()
    return json.loads(text)


def _contains_invented_claim(body: str, profile: FreelancerProfile | None) -> bool:
    forbidden = (
        "гарантирую",
        "100%",
        "уже делал для google",
        "топ-1",
        "бесплатно сделаю",
    )
    lowered = body.lower()
    if any(item in lowered for item in forbidden):
        return True
    if profile is None:
        return False
    known = " ".join(
        [
            profile.specialization or "",
            " ".join(profile.skills or []),
            json.dumps(profile.portfolio or [], ensure_ascii=False),
        ]
    ).lower()
    # Flag only if the draft cites a numeric years-of-experience not present in profile.
    years = re.findall(r"(\d+)\s+лет", lowered)
    return bool(years and not any(year in known for year in years) and "лет" not in known)


def heuristic_drafts(job: Job, analysis: AnalysisResult, profile: FreelancerProfile | None) -> DraftBundle:
    skill = (analysis.matching_skills or (profile.skills if profile else []) or ["профильную задачу"])[0]
    requirement = (analysis.scope or [job.title])[0]
    portfolio = ""
    used: list[str] = []
    missing: list[str] = []
    if profile and profile.portfolio:
        case = profile.portfolio[0]
        title = case.get("title") if isinstance(case, dict) else str(case)
        portfolio = f"Близкий кейс: {title}."
        used.append(str(title))
    else:
        missing.append("portfolio_case")
    if profile and profile.skills:
        used.extend(profile.skills[:4])
    else:
        missing.append("skills")

    question = ""
    if analysis.missing_information:
        question = f" Уточните, пожалуйста: {analysis.missing_information[0].rstrip('?')}?"

    short = (
        f"По задаче «{job.title.strip()}» вижу акцент на {requirement}. "
        f"Могу закрыть это на стороне {skill}. {portfolio} "
        f"Предлагаю сначала согласовать объём и критерии приёмки, затем сразу перейти к первому рабочему шагу.{question}"
    ).strip()
    standard = (
        f"В заказе важно: {requirement}. Я бы начал с короткой декомпозиции и проверки вводных, "
        f"чтобы не раздувать объём. Рабочий стек пересекается с {skill}. {portfolio} "
        f"Следующий шаг — сверка ожидаемого результата и ограничений, после этого могу прислать план работ.{question}"
    ).strip()
    technical = (
        f"Ключевое требование: {requirement}. Практический план: зафиксировать входные данные, "
        f"собрать минимальный рабочий контур на {skill}, затем итерациями закрыть остальной объём. "
        f"{portfolio} Не обещаю сроки и стоимость без уточнения границ задачи. "
        f"Готов продолжить на странице заказа после сверки критериев.{question}"
    ).strip()
    variants = [
        DraftVariant(style="short", body=short, used_profile_facts=used, missing_facts=missing),
        DraftVariant(style="standard", body=standard, used_profile_facts=used, missing_facts=missing),
        DraftVariant(style="technical", body=technical, used_profile_facts=used, missing_facts=missing),
    ]
    return DraftBundle(variants=variants, used_profile_facts=used, missing_facts=missing)


class ResponseGenerator:
    def __init__(self, provider: LLMProvider | None) -> None:
        self._provider = provider

    async def generate(
        self, job: Job, analysis: AnalysisResult, profile: FreelancerProfile | None
    ) -> DraftBundle:
        if self._provider is None:
            return heuristic_drafts(job, analysis, profile)

        job_payload = {
            "title": job.title,
            "description": job.description[:4000],
            "category": job.category,
            "budget_raw": job.budget_raw,
        }
        user_prompt = build_response_user_prompt(
            job_payload, analysis.model_dump(), _safe_profile(profile)
        )
        try:
            raw = await self._provider.complete_json(system=RESPONSE_SYSTEM, user=user_prompt)
            data = _extract_json(raw)
            bundle = DraftBundle.model_validate(data)
        except (LLMUnavailableError, ValidationError, json.JSONDecodeError, TypeError):
            return heuristic_drafts(job, analysis, profile)

        cleaned: list[DraftVariant] = []
        for variant in bundle.variants:
            if _contains_invented_claim(variant.body, profile):
                fallback = heuristic_drafts(job, analysis, profile)
                match = next((item for item in fallback.variants if item.style == variant.style), fallback.variants[0])
                cleaned.append(match)
            else:
                cleaned.append(variant)
        if not cleaned:
            return heuristic_drafts(job, analysis, profile)
        styles = {item.style for item in cleaned}
        if styles != {"short", "standard", "technical"}:
            return heuristic_drafts(job, analysis, profile)
        return DraftBundle(
            variants=cleaned,
            used_profile_facts=bundle.used_profile_facts,
            missing_facts=bundle.missing_facts,
        )
