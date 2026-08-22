"""Chapter 6.5 real-telemetry computation: pure, input-dependent verdicts
over real signal shapes -- `engine.telemetry.rules`."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from engine.recovery.matrix import decide
from engine.telemetry.model import ACTUAL_COST_GAP_DISCLOSED
from engine.telemetry.rules import compute_outcome

_STARTED = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
_ENDED = datetime(2026, 1, 1, 0, 0, 30, tzinfo=UTC)


def test_passed_outcome_has_no_recovery_signal() -> None:
    result = compute_outcome(
        status="PASSED",
        confidence=1.0,
        rework_count=2,
        recovery_decision=None,
        started_at=_STARTED,
        ended_at=_ENDED,
    )

    assert result.actual_verified_outcome == "PASSED"
    assert result.rework_count == 2
    assert result.escalated is False
    assert result.human_intervention_required is False
    assert result.recovery_action is None
    assert result.failure_class is None
    assert result.elapsed_seconds == pytest.approx(30.0)
    assert ACTUAL_COST_GAP_DISCLOSED in result.disclosed_gaps


def test_failed_outcome_first_occurrence_is_repair_not_human() -> None:
    decision = decide("VERIFICATION_FAILURE", occurrence_count=1)

    result = compute_outcome(
        status="FAILED",
        confidence=0.0,
        rework_count=1,
        recovery_decision=decision,
        started_at=_STARTED,
        ended_at=_ENDED,
    )

    assert result.actual_verified_outcome == "FAILED"
    assert result.recovery_action == "repair"
    assert result.escalated is False
    assert result.human_intervention_required is False
    assert result.failure_class == "VERIFICATION_FAILURE"


def test_failed_outcome_repeated_occurrence_escalates_to_replan_and_human() -> None:
    """Chapter 12.3: repeated VERIFICATION_FAILURE replans, which is a
    real human-intervention signal from the recovery matrix, not a guess
    this module invents on its own."""
    decision = decide("VERIFICATION_FAILURE", occurrence_count=2)

    result = compute_outcome(
        status="FAILED",
        confidence=0.5,
        rework_count=2,
        recovery_decision=decision,
        started_at=_STARTED,
        ended_at=_ENDED,
    )

    assert result.recovery_action == "replan"
    assert result.human_intervention_required is True


def test_unended_run_reports_no_fabricated_elapsed_time() -> None:
    result = compute_outcome(
        status="PASSED",
        confidence=1.0,
        rework_count=0,
        recovery_decision=None,
        started_at=_STARTED,
        ended_at=None,
    )

    assert result.elapsed_seconds is None


def test_failed_status_without_recovery_decision_is_rejected() -> None:
    with pytest.raises(ValueError, match="FAILED"):
        compute_outcome(
            status="FAILED",
            confidence=0.0,
            rework_count=1,
            recovery_decision=None,
            started_at=_STARTED,
            ended_at=_ENDED,
        )


def test_passed_status_with_recovery_decision_is_rejected() -> None:
    decision = decide("VERIFICATION_FAILURE", occurrence_count=1)
    with pytest.raises(ValueError, match="PASSED"):
        compute_outcome(
            status="PASSED",
            confidence=1.0,
            rework_count=0,
            recovery_decision=decision,
            started_at=_STARTED,
            ended_at=_ENDED,
        )
