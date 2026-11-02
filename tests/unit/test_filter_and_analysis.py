from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.db.models import Job
from app.domain.enums import SourceCode
from app.domain.models import NormalizedBudget, NormalizedJob
from app.llm.schemas import AnalysisResult
from app.services.analysis_service import AnalysisService, keyword_fallback
from app.services.filtering import quick_filter
from app.services.response_generator import ResponseGenerator, heuristic_drafts


def _job(**kwargs) -> NormalizedJob:
    base = dict(
        source=SourceCode.FL_RSS,
        external_id="1",
        url="https://www.fl.ru/projects/1/x.html",
        canonical_url="https://www.fl.ru/projects/1/x.html",
        title="Python FastAPI бот",
        description="Нужен Python и FastAPI разработчик без бесплатного теста",
        category="Программирование / Веб-программирование",
        skills=["Python"],
        budget=NormalizedBudget(amount=25000, currency="RUB", raw="25000"),
        published_at=datetime.now(timezone.utc),
        discovered_at=datetime.now(timezone.utc),
        content_hash="abc",
    )
    base.update(kwargs)
    return NormalizedJob(**base)


def test_filter_stop_word_and_keyword() -> None:
    profile = SimpleNamespace(
        stop_words=["отзыв"],
        excluded_categories=[],
        min_budget=5000,
        skills=["Python"],
        keywords=["python", "fastapi"],
    )
    ok = quick_filter(_job(), profile)
    assert ok.passed
    blocked = quick_filter(
        _job(title="Написать отзыв", description="нужен отзыв", category="Тексты"),
        profile,
    )
    assert not blocked.passed
    cheap = quick_filter(_job(budget=NormalizedBudget(amount=100, currency="RUB")), profile)
    assert not cheap.passed


def test_analysis_schema_and_fallback() -> None:
    payload = {
        "summary": "Бот на FastAPI",
        "required_skills": ["Python", "FastAPI"],
        "matching_skills": ["Python"],
        "missing_skills": ["FastAPI"],
        "scope": ["API"],
        "budget": {"amount": 25000, "currency": "RUB", "assessment": "adequate", "evidence": "25000"},
        "deadline_assessment": "unknown",
        "competition": {"value": None, "source_provided": False},
        "risk_flags": [],
        "score": 81,
        "risk_penalty": 0,
        "decision": "apply",
        "reasons_for": ["стек совпадает"],
        "reasons_against": [],
        "missing_information": [],
        "clarifying_questions": [],
        "confidence": 0.7,
        "evidence_quotes": ["Python и FastAPI"],
    }
    result = AnalysisResult.model_validate(payload)
    assert result.score == 81

    job = Job(
        source="fl_rss",
        external_id="1",
        url="https://www.fl.ru/projects/1/x.html",
        canonical_url="https://www.fl.ru/projects/1/x.html",
        title="Python бот",
        description="Сделать бота на Python. Можно бесплатное тестовое задание.",
        category="Программирование",
        skills=["Python"],
        discovered_at=datetime.now(timezone.utc),
        content_hash="x",
        extras={},
        status="new",
    )
    profile = SimpleNamespace(skills=["Python", "FastAPI"], portfolio=[], specialization="Python")
    fallback = keyword_fallback(job, profile)
    assert fallback.fallback is True
    assert fallback.risk_penalty >= 12
    assert any(flag.code == "UNPAID_TEST" for flag in fallback.risk_flags)


@pytest.mark.asyncio
async def test_analysis_without_llm_uses_fallback() -> None:
    service = AnalysisService(None)
    job = Job(
        source="fl_rss",
        external_id="1",
        url="https://www.fl.ru/projects/1/x.html",
        canonical_url="https://www.fl.ru/projects/1/x.html",
        title="Python FastAPI",
        description="Нужен Python разработчик",
        category="Программирование",
        skills=["Python"],
        discovered_at=datetime.now(timezone.utc),
        content_hash="x",
        extras={},
        status="new",
    )
    profile = SimpleNamespace(skills=["Python"], portfolio=[], specialization="Python")
    result = await service.analyze(job, profile)
    assert result.fallback is True


@pytest.mark.asyncio
async def test_drafts_do_not_invent_portfolio() -> None:
    job = Job(
        source="fl_rss",
        external_id="1",
        url="https://www.fl.ru/projects/1/x.html",
        canonical_url="https://www.fl.ru/projects/1/x.html",
        title="Python FastAPI бот",
        description="Нужен API на FastAPI",
        category="Программирование",
        skills=["Python"],
        discovered_at=datetime.now(timezone.utc),
        content_hash="x",
        extras={},
        status="analyzed",
    )
    analysis = AnalysisResult(summary="API", matching_skills=["Python"], scope=["FastAPI API"])
    profile = SimpleNamespace(
        skills=["Python", "FastAPI"],
        portfolio=[{"title": "Бот учёта заказов на FastAPI"}],
        specialization="Python",
        availability="",
        tone="professional",
        sample_responses=[],
        languages=["ru"],
        experience_level="",
    )
    bundle = await ResponseGenerator(None).generate(job, analysis, profile)
    styles = {item.style for item in bundle.variants}
    assert styles == {"short", "standard", "technical"}
    joined = " ".join(item.body.lower() for item in bundle.variants)
    assert "гарантирую" not in joined
    assert "бесплатно сделаю" not in joined
    assert "fastapi" in joined
    heuristic = heuristic_drafts(job, analysis, profile)
    assert "Бот учёта заказов на FastAPI" in heuristic.variants[0].body
