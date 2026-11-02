from __future__ import annotations

from datetime import datetime
from html import escape

from app.db.models import Job, JobAnalysis
from app.llm.schemas import AnalysisResult, DraftBundle

PRIORITY = {
    "apply": "высокий приоритет",
    "consider": "рассмотреть",
    "manual_review": "ручная проверка",
    "skip": "скорее пропустить",
}


def fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "не указано"
    return value.strftime("%Y-%m-%d %H:%M UTC")


def job_card(job: Job, analysis: AnalysisResult | JobAnalysis | None) -> str:
    if isinstance(analysis, JobAnalysis):
        score = analysis.score
        decision = analysis.decision
        summary = analysis.summary
        fallback = analysis.fallback
        result = analysis.result or {}
        reasons_for = result.get("reasons_for") or []
        reasons_against = result.get("reasons_against") or []
        risks = result.get("risk_flags") or []
    elif analysis is not None:
        score = analysis.score
        decision = analysis.decision
        summary = analysis.summary
        fallback = analysis.fallback
        reasons_for = analysis.reasons_for
        reasons_against = analysis.reasons_against
        risks = [flag.model_dump() for flag in analysis.risk_flags]
    else:
        score = 0
        decision = "manual_review"
        summary = job.description[:240]
        fallback = True
        reasons_for = []
        reasons_against = []
        risks = []

    budget = job.budget_raw or (
        f"{job.budget_amount} {job.budget_currency}" if job.budget_amount else "не указан"
    )
    risk_lines = [
        f"- {escape(str(item.get('code')))}: {escape(str(item.get('evidence', '')))[:180]}"
        for item in risks[:4]
    ]
    for_lines = "\n".join(f"- {escape(str(item))}" for item in reasons_for[:3]) or "- нет"
    against_lines = "\n".join(f"- {escape(str(item))}" for item in reasons_against[:3]) or "- нет"
    analysis_note = "AI-анализ недоступен, показан keyword fallback." if fallback else "AI-анализ выполнен."
    return (
        f"<b>{escape(job.title)}</b>\n"
        f"Площадка: {escape(job.source)}\n"
        f"Категория: {escape(job.category or 'не указана')}\n"
        f"Бюджет: {escape(str(budget))}\n"
        f"Опубликован: {fmt_dt(job.published_at)}\n"
        f"Обнаружен: {fmt_dt(job.discovered_at)}\n"
        f"Оценка: <b>{score}/100</b> — {PRIORITY.get(decision, decision)}\n"
        f"{analysis_note}\n\n"
        f"{escape((summary or '')[:500])}\n\n"
        f"<b>Почему подходит</b>\n{for_lines}\n"
        f"<b>Риски / против</b>\n{against_lines}\n"
        + ("\n".join(risk_lines) + "\n" if risk_lines else "")
        + f"\n<a href=\"{escape(job.url)}\">Открыть исходный заказ</a>"
    )


def drafts_message(bundle: DraftBundle) -> str:
    parts = ["<b>Черновики первого отклика</b>", "Бот ничего не отправляет на площадку."]
    if bundle.used_profile_facts:
        parts.append("Использованы факты профиля: " + escape(", ".join(bundle.used_profile_facts[:8])))
    if bundle.missing_facts:
        parts.append("Не хватает в профиле: " + escape(", ".join(bundle.missing_facts[:8])))
    for variant in bundle.variants:
        parts.append(f"\n<b>{variant.style}</b>\n{escape(variant.body)}")
    return "\n".join(parts)


def profile_message(profile) -> str:  # noqa: ANN001
    skills = ", ".join(profile.skills or []) or "не заданы"
    keywords = ", ".join(profile.keywords or []) or "не заданы"
    stops = ", ".join(profile.stop_words or []) or "нет"
    portfolio = profile.portfolio or []
    cases = ", ".join(
        (item.get("title") if isinstance(item, dict) else str(item)) for item in portfolio[:5]
    ) or "нет подтверждённых кейсов"
    min_budget = profile.min_budget if profile.min_budget is not None else "не задан"
    return (
        "<b>Профиль исполнителя</b>\n"
        f"Специализация: {escape(profile.specialization or 'не задана')}\n"
        f"Навыки: {escape(skills)}\n"
        f"Ключевые слова: {escape(keywords)}\n"
        f"Стоп-слова: {escape(stops)}\n"
        f"Мин. бюджет: {escape(str(min_budget))} {escape(profile.currency)}\n"
        f"Тон: {escape(profile.tone)}\n"
        f"Кейсы: {escape(cases)}"
    )
