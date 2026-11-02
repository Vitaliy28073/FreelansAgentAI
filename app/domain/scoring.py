from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreWeights:
    skills: int = 30
    portfolio: int = 15
    budget: int = 15
    clarity: int = 10
    reliability: int = 10
    deadline: int = 10
    competition: int = 5
    strategic: int = 5
    max_risk_penalty: int = 30


DEFAULT_WEIGHTS = ScoreWeights()


def clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def apply_risk_penalty(base: float, penalty: float, max_penalty: int = 30) -> int:
    return clamp_score(base - min(max(penalty, 0), max_penalty))


def decision_from_score(score: int, *, full_monitoring: bool = False) -> str:
    if score >= 80:
        return "apply"
    if score >= 65:
        return "consider"
    if score >= 45:
        return "manual_review"
    return "skip" if not full_monitoring else "manual_review"
