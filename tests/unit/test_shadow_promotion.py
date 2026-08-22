"""Shadow-mode policy promotion (comparable-systems adoption #8) --
pure evaluation tests over real `RoutingDecisionOutcome` shapes.

No live routing code is imported or exercised here beyond the contract
object; `engine.simulation.shadow_promotion` reads recorded outcomes and
measures deltas, nothing else.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from engine.contracts.routing_decision_outcome import RoutingDecisionOutcome
from engine.simulation.shadow_promotion import (
    SHADOW_PROMOTION_RUN_KIND,
    PolicyMetrics,
    ShadowPromotionRequest,
    evaluate_shadow_promotion,
    measure,
    replay,
)

_NOW = datetime(2026, 8, 22, tzinfo=UTC)


def _outcome(
    index: int,
    *,
    passed: bool,
    confidence: float,
    elapsed: float,
    escalated: bool = False,
    human_required: bool = False,
) -> RoutingDecisionOutcome:
    identity = UUID(int=index)
    return RoutingDecisionOutcome(
        outcome_id=UUID(int=index + 100),
        tenant_id=identity,
        project_id=UUID(int=index + 200),
        mission_id=UUID(int=index + 300),
        task_id=UUID(int=index + 400),
        route_decision_id=UUID(int=index + 500),
        task_attempt_id=UUID(int=index + 600),
        verification_run_id=UUID(int=index + 700),
        actual_verified_outcome="PASSED" if passed else "FAILED",
        verification_confidence=confidence,
        rework_count=0,
        escalated=escalated,
        human_intervention_required=human_required,
        recovery_action=None if passed else "repair",
        failure_class=None,
        elapsed_seconds=elapsed,
        context_package_id=UUID(int=index + 800),
        capability_set=["worker.invoke"],
        disclosed_gaps=["gap"],
        created_at=_NOW,
        updated_at=_NOW,
    )


def _outcomes(
    specs: list[tuple[bool, float, float, bool]],
) -> list[RoutingDecisionOutcome]:
    return [
        _outcome(
            index,
            passed=passed,
            confidence=confidence,
            elapsed=elapsed,
            escalated=gate_failed,
            human_required=gate_failed,
        )
        for index, (passed, confidence, elapsed, gate_failed) in enumerate(specs)
    ]


#: (passed, confidence, elapsed_seconds, gate_failed)
BASELINE_MIX = [
    (True, 1.0, 10.0, False),
    (True, 1.0, 12.0, False),
    (False, 0.2, 40.0, True),
    (True, 1.0, 11.0, False),
]


def test_replay_honours_candidate_confidence_floor() -> None:
    outcomes = _outcomes(BASELINE_MIX)
    replayed = replay({"accept_confidence_floor": 0.9}, outcomes)
    assert [item.accepted for item in replayed] == [
        True,
        True,
        False,
        True,
    ]
    stricter = replay({"accept_confidence_floor": 1.0}, outcomes)
    assert [item.accepted for item in stricter] == [
        True,
        True,
        False,
        True,
    ]
    # No floor: every PASSED row is accepted, gate-failed or not.
    loose = replay({}, outcomes)
    assert [item.accepted for item in loose] == [True, True, False, True]


def test_measure_aggregates_real_rates() -> None:
    metrics = measure(replay({"accept_confidence_floor": 0.9}, _outcomes(BASELINE_MIX)))
    assert metrics.decisions == 4
    assert metrics.accept_rate == pytest.approx(3 / 4)
    # Gate failures are measured over the accepted set only.
    assert metrics.gate_fail_rate == 0.0
    assert metrics.mean_cost == pytest.approx((10.0 + 12.0 + 11.0) / 3)
    assert metrics.cost_samples == 3


def test_measure_without_cost_samples_reports_none_not_zero() -> None:
    metrics = measure(replay({}, []))
    assert metrics.mean_cost is None
    assert metrics.decisions == 0


def test_promotion_requires_accept_rate_win() -> None:
    outcomes = _outcomes(BASELINE_MIX)
    request = ShadowPromotionRequest(
        candidate_policy={"accept_confidence_floor": 0.9},
        max_cost_regression=0.25,
        rollback_trigger=lambda metrics: False,
    )
    # The candidate's floor accepts the same three decisions as the
    # default baseline floor (0.0 accepts the same PASSED set); the
    # accept-rate delta is zero, so promotion must be refused.
    decision = evaluate_shadow_promotion(request, outcomes)
    assert decision.promoted is False
    assert any("did not improve" in reason for reason in decision.reasons)


def test_promotion_succeeds_on_real_improvement_within_cost() -> None:
    # Baseline (floor 0.0) accepts all four PASSED rows; the candidate's
    # 0.9 floor drops the two low-confidence passes, so accept rate rises
    # from 4/5 to... no: both floors accept the same PASSED set. Use a
    # baseline floor that rejects one passable row the candidate keeps.
    outcomes = _outcomes(
        [
            (True, 1.0, 10.0, False),
            (True, 0.95, 12.0, False),
            (True, 1.0, 11.0, False),
            (False, 0.2, 40.0, True),
        ]
    )
    fired_holder: list[PolicyMetrics] = []

    def trigger(metrics: PolicyMetrics) -> bool:
        fired_holder.append(metrics)
        return False

    request = ShadowPromotionRequest(
        candidate_policy={},
        max_cost_regression=1.0,
        rollback_trigger=trigger,
        baseline_policy={"accept_confidence_floor": 0.99},
    )
    decision = evaluate_shadow_promotion(request, outcomes)
    assert decision.promoted is True
    assert decision.accept_rate_delta > 0
    assert decision.rollback_trigger_fired is False
    # The trigger was genuinely consulted with the candidate's metrics.
    assert len(fired_holder) == 1
    assert fired_holder[0] == decision.candidate
    assert "actual_token_cost" in decision.cost_basis


def test_promotion_refused_when_cost_regression_exceeds_threshold() -> None:
    # Baseline accepts everything (no floor); the candidate's floor drops
    # the two cheap low-confidence rows and keeps only the slow expensive
    # ones, so its accepted-set mean cost is far above baseline.
    outcomes = _outcomes(
        [
            (True, 0.95, 10.0, False),
            (True, 0.95, 12.0, False),
            (True, 1.0, 500.0, False),
            (True, 1.0, 600.0, False),
        ]
    )
    request = ShadowPromotionRequest(
        candidate_policy={"accept_confidence_floor": 0.99},
        max_cost_regression=0.05,
        rollback_trigger=lambda metrics: False,
    )
    decision = evaluate_shadow_promotion(request, outcomes)
    assert decision.promoted is False
    assert decision.cost_delta is not None and decision.cost_delta > 0
    assert any("ceiling" in reason for reason in decision.reasons)


def test_promotion_refused_when_rollback_trigger_fires() -> None:
    gate_heavy = [(True, 1.0, 10.0, True), (True, 1.0, 12.0, True)]
    outcomes = _outcomes(gate_heavy)
    request = ShadowPromotionRequest(
        candidate_policy={"accept_confidence_floor": 0.9},
        max_cost_regression=1.0,
        rollback_trigger=lambda metrics: metrics.gate_fail_rate > 0.2,
    )
    decision = evaluate_shadow_promotion(request, outcomes)
    assert decision.promoted is False
    assert decision.rollback_trigger_fired is True
    assert any("rollback trigger" in reason for reason in decision.reasons)


def test_no_outcomes_refuses_to_promote() -> None:
    request = ShadowPromotionRequest(
        candidate_policy={"accept_confidence_floor": 0.9},
        max_cost_regression=0.1,
        rollback_trigger=lambda metrics: False,
    )
    decision = evaluate_shadow_promotion(request, [])
    assert decision.promoted is False
    assert decision.accept_rate_delta == 0.0
    assert decision.cost_delta is None


RUN_KIND = SHADOW_PROMOTION_RUN_KIND


def test_run_kind_discriminator_value_is_stable() -> None:
    assert RUN_KIND == "shadow_promotion"
