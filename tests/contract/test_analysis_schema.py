from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.llm.schemas import AnalysisResult, DraftBundle


def test_analysis_rejects_bad_score() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate({"summary": "x", "decision": "nope"})


def test_draft_bundle_requires_variants() -> None:
    bundle = DraftBundle.model_validate(
        {
            "variants": [
                {"style": "short", "body": "a"},
                {"style": "standard", "body": "b"},
                {"style": "technical", "body": "c"},
            ]
        }
    )
    assert len(bundle.variants) == 3
