"""Schema tests for ReplanDecision (Chapter 4.6 / DDE-024)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from engine.contracts.replan_decision import ReplanDecision
from engine.core.ids import uuid7


def test_replan_decision_requires_explanations() -> None:
    with pytest.raises(ValidationError):
        ReplanDecision.model_validate(
            {
                "graph_id": uuid7(),
                "trigger": "operator",
                "dispositions": {},
            }
        )


def test_replan_decision_accepts_chapter_4_6_dispositions() -> None:
    decision = ReplanDecision.model_validate(
        {
            "graph_id": uuid7(),
            "trigger": "WRONG_PRODUCT",
            "dispositions": {str(uuid7()): "REVERT"},
            "explanations": {str(uuid7()): "merged output must be undone"},
        }
    )
    assert decision.trigger == "WRONG_PRODUCT"
