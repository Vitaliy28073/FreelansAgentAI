from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class BudgetAssessment(BaseModel):
    amount: float | None = None
    currency: str | None = None
    assessment: Literal["adequate", "low", "high", "unknown"] = "unknown"
    evidence: str = ""


class CompetitionInfo(BaseModel):
    value: int | None = None
    source_provided: bool = False


class RiskFlag(BaseModel):
    code: str
    severity: Literal["low", "medium", "high"]
    evidence: str
    recommendation: str


class AnalysisResult(BaseModel):
    summary: str
    required_skills: list[str] = Field(default_factory=list)
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    budget: BudgetAssessment = Field(default_factory=BudgetAssessment)
    deadline_assessment: Literal["realistic", "tight", "unrealistic", "unknown"] = "unknown"
    competition: CompetitionInfo = Field(default_factory=CompetitionInfo)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    score: int = 0
    risk_penalty: int = 0
    decision: Literal["apply", "consider", "skip", "manual_review"] = "manual_review"
    reasons_for: list[str] = Field(default_factory=list)
    reasons_against: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    evidence_quotes: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, int | str] = Field(default_factory=dict)
    fallback: bool = False

    @field_validator("score")
    @classmethod
    def score_range(cls, value: int) -> int:
        return max(0, min(100, value))

    @field_validator("risk_penalty")
    @classmethod
    def penalty_range(cls, value: int) -> int:
        return max(0, min(30, value))

    @field_validator("confidence")
    @classmethod
    def confidence_range(cls, value: float) -> float:
        return max(0.0, min(1.0, value))

    @field_validator("clarifying_questions")
    @classmethod
    def max_questions(cls, value: list[str]) -> list[str]:
        return value[:3]


class DraftVariant(BaseModel):
    style: Literal["short", "standard", "technical"]
    body: str
    used_profile_facts: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)


class DraftBundle(BaseModel):
    variants: list[DraftVariant]
    used_profile_facts: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
