"""Chapter 6.9 activation gates: refuse when unmet.

These tests exist so a later mission cannot promote a learned router
from training metrics or from an empty eligible population. The S7
exit criterion ('refusal to activate when unmet') is this module.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from engine.contracts.experience_record import ExperienceRecord
from engine.core.ids import uuid7
from engine.learning.activation import (
    can_transition,
    evaluate_activation_gates,
    last_certified_mode,
)


def _record(*, eligible: bool = True) -> ExperienceRecord:
    now = datetime.now(UTC)
    return ExperienceRecord(
        experience_id=uuid7(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        experience_origin="real",
        routing_policy_version="deterministic-v1",
        candidate_set_hash="abc",
        selection_propensity=1.0,
        prediction_vector={},
        observed_outcome_vector={},
        verification_confidence=1.0,
        failure_attribution="none",
        attribution_confidence=1.0,
        holdout_partition="train",
        promotion_evidence_refs=[],
        eligible_for_routing_training=eligible,
        eligibility_reasons=["eligible"] if eligible else ["origin_not_real"],
        down_weighted=False,
        promotion_state="unpromoted",
        created_at=now,
        updated_at=now,
        verification_run_id=uuid7(),
    )


def test_empty_population_refuses_shadow_learning() -> None:
    verdict = evaluate_activation_gates(
        records=[],
        workload_classes=[],
        current_mode="deterministic",
        requested_mode="shadow_learning",
    )
    assert verdict.allowed is False
    assert "eligible_real_attempts_global_below_threshold" in verdict.refused_reasons


def test_simulation_records_do_not_count_toward_volume() -> None:
    now = datetime.now(UTC)
    sim = ExperienceRecord(
        experience_id=uuid7(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        experience_origin="simulation",
        routing_policy_version="deterministic-v1",
        candidate_set_hash="abc",
        selection_propensity=1.0,
        prediction_vector={},
        observed_outcome_vector={},
        verification_confidence=0.0,
        failure_attribution="none",
        attribution_confidence=0.0,
        holdout_partition="train",
        promotion_evidence_refs=[],
        eligible_for_routing_training=False,
        eligibility_reasons=["experience_origin=simulation: excluded by construction"],
        down_weighted=False,
        promotion_state="unpromoted",
        created_at=now,
        updated_at=now,
        routing_simulation_run_id=uuid7(),
    )
    verdict = evaluate_activation_gates(
        records=[sim],
        workload_classes=["bulk_implementation"],
        current_mode="deterministic",
        requested_mode="shadow_learning",
    )
    assert verdict.allowed is False
    assert "eligible_real_attempts_global_below_threshold" in verdict.refused_reasons


def test_skipping_to_canary_from_deterministic_is_illegal() -> None:
    verdict = evaluate_activation_gates(
        records=[],
        workload_classes=[],
        current_mode="deterministic",
        requested_mode="canary",
    )
    assert verdict.allowed is False
    assert "illegal_mode_transition" in verdict.refused_reasons


def test_calibration_without_a_real_score_is_insufficient_not_a_pass() -> None:
    verdict = evaluate_activation_gates(
        records=[_record() for _ in range(5)],
        workload_classes=["bulk_implementation"] * 5,
        current_mode="deterministic",
        requested_mode="shadow_learning",
        brier=None,
        ece=None,
    )
    assert verdict.allowed is False
    assert "calibration_brier_insufficient_evidence" in verdict.refused_reasons
    assert "calibration_ece_insufficient_evidence" in verdict.refused_reasons


def test_rollback_returns_to_last_certified_never_untested() -> None:
    assert last_certified_mode(current="canary", certified="deterministic") == (
        "deterministic"
    )
    assert last_certified_mode(current="shadow_learning", certified=None) == (
        "deterministic"
    )


def test_forward_one_step_is_legal() -> None:
    assert can_transition(current="deterministic", target="shadow_learning")
    assert can_transition(current="shadow_learning", target="canary")
    assert can_transition(current="canary", target="promoted_historical")
    assert not can_transition(current="deterministic", target="promoted_historical")
