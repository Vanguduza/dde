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


def test_replay_keeps_decision_and_truth_independent() -> None:
    outcomes = _outcomes(BASELINE_MIX)
    replayed = replay({"accept_confidence_floor": 0.9}, outcomes)
    # The floor-0.9 policy routes the three confident rows and rejects
    # the low-confidence failure; ground truth stays on its own axis.
    assert [(item.routed, item.actual_passed) for item in replayed] == [
        (True, True),
        (True, True),
        (False, False),
        (True, True),
    ]
    # No floor: every row is routed, including the doomed one -- a
    # routing decision is confidence-vs-floor, never outcome-dependent.
    loose = replay({}, outcomes)
    assert [item.routed for item in loose] == [True, True, True, True]
    assert loose[2].actual_passed is False


def test_measure_counts_all_four_quadrants() -> None:
    # floor 0.5 over: pass@0.8, fail@0.9 (wasted), pass@0.3 (missed),
    # fail@0.1 (correct rejection).
    outcomes = _outcomes(
        [
            (True, 0.8, 10.0, False),
            (False, 0.9, 40.0, True),
            (True, 0.3, 20.0, False),
            (False, 0.1, 30.0, True),
        ]
    )
    metrics = measure(replay({"accept_confidence_floor": 0.5}, outcomes))
    assert metrics.decisions == 4
    assert metrics.successes == 1
    assert metrics.wasted_accepts == 1
    assert metrics.missed_passes == 1
    assert metrics.correct_rejections == 1
    assert metrics.routed_rate == pytest.approx(0.5)
    assert metrics.success_yield == pytest.approx(1 / 4)
    assert metrics.wasted_accept_rate == pytest.approx(1 / 2)
    # Gate failures are measured over the routed set only.
    assert metrics.gate_fail_rate == pytest.approx(0.5)


def test_measure_costs_include_failed_routed_tasks() -> None:
    # The routed set spans a cheap success and an expensive failure; the
    # failed task's elapsed time burns just as surely as the pass's.
    outcomes = _outcomes(
        [
            (True, 1.0, 10.0, False),
            (False, 1.0, 40.0, True),
            (False, 0.1, 900.0, True),
        ]
    )
    metrics = measure(replay({"accept_confidence_floor": 0.5}, outcomes))
    assert metrics.cost_samples == 2
    assert metrics.mean_cost == pytest.approx((10.0 + 40.0) / 2)
    assert metrics.wasted_accept_rate == pytest.approx(0.5)


def test_measure_without_cost_samples_reports_none_not_zero() -> None:
    metrics = measure(replay({}, []))
    assert metrics.mean_cost is None
    assert metrics.decisions == 0


def test_permissive_candidate_routing_only_failures_is_refused() -> None:
    """Regression test for the accept-rate promotion flaw.

    Under the old semantics `accepted = passed AND confidence >= floor`,
    so this candidate -- whose newly routed tasks ALL fail -- could never
    lose a metric by accepting doomed work, and any floor below the
    baseline's mechanically won promotion. Under the honest semantics its
    wasted accepts rise with zero yield gain, so it must be refused.
    """
    outcomes = _outcomes(
        [
            (True, 0.99, 10.0, False),  # both floors route; passes
            (False, 0.7, 40.0, True),  # only candidate routes; fails
            (False, 0.8, 45.0, True),  # only candidate routes; fails
        ]
    )
    request = ShadowPromotionRequest(
        candidate_policy={"accept_confidence_floor": 0.6},
        max_cost_regression=1.0,
        rollback_trigger=lambda metrics: False,
        baseline_policy={"accept_confidence_floor": 0.95},
        wasted_accept_tolerance=0.0,
    )
    decision = evaluate_shadow_promotion(request, outcomes)
    assert decision.promoted is False
    assert decision.candidate.missed_passes == 0
    assert decision.candidate.wasted_accepts == 2
    assert decision.baseline.wasted_accepts == 0
    assert decision.wasted_accept_delta > 0
    assert decision.success_yield_delta <= 0
    assert any("success_yield" in reason for reason in decision.reasons)
    assert any("wasted_accept_rate" in reason for reason in decision.reasons)
    # The cost gate independently refuses too: the candidate's routed set
    # carries the two slow failures, so mean routed cost regresses hard.
    assert decision.cost_delta is not None and decision.cost_delta > 0


def test_permissive_candidate_with_real_passes_is_promoted() -> None:
    """Legit throughput gain: the candidate's lower floor picks up rows
    that genuinely pass, so success_yield rises honestly."""
    outcomes = _outcomes(
        [
            (True, 1.0, 10.0, False),
            (True, 0.92, 12.0, False),  # only candidate routes; passes
            (True, 0.93, 11.0, False),  # only candidate routes; passes
            (False, 0.2, 40.0, True),  # neither routes
        ]
    )
    request = ShadowPromotionRequest(
        candidate_policy={"accept_confidence_floor": 0.9},
        max_cost_regression=1.0,
        rollback_trigger=lambda metrics: False,
        baseline_policy={"accept_confidence_floor": 0.95},
    )
    decision = evaluate_shadow_promotion(request, outcomes)
    assert decision.promoted is True
    assert decision.success_yield_delta == pytest.approx(0.5)
    assert decision.candidate.success_yield == pytest.approx(0.75)
    assert decision.routed_rate_delta > 0
    assert decision.wasted_accept_delta <= 0
    assert "actual_token_cost" in decision.cost_basis


def test_stricter_candidate_trading_yield_for_fewer_wastes_is_refused() -> None:
    # Both policies route all four rows; the stricter one cannot change
    # what already happened, so yield is flat at best while misses grow.
    outcomes = _outcomes(
        [
            (True, 1.0, 10.0, False),
            (True, 0.8, 12.0, False),
            (False, 0.3, 40.0, True),
            (False, 0.2, 41.0, True),
        ]
    )
    request = ShadowPromotionRequest(
        candidate_policy={"accept_confidence_floor": 0.95},
        max_cost_regression=1.0,
        rollback_trigger=lambda metrics: False,
        baseline_policy={"accept_confidence_floor": 0.5},
    )
    decision = evaluate_shadow_promotion(request, outcomes)
    assert decision.promoted is False
    assert decision.success_yield_delta <= 0
    assert decision.candidate.missed_passes >= decision.baseline.missed_passes
    assert any("success_yield" in reason for reason in decision.reasons)


def test_wasted_rate_beyond_tolerance_refused_despite_yield_gain() -> None:
    # Candidate gains one genuine new pass AND takes on two new doomed
    # rows; yield rises, but the wasted-accept rate explodes past the
    # caller's tolerance, so promotion is refused anyway.
    outcomes = _outcomes(
        [
            (True, 1.0, 10.0, False),  # both route; passes
            (True, 0.92, 12.0, False),  # only candidate; passes
            (False, 0.85, 40.0, True),  # only candidate; fails
            (False, 0.80, 45.0, True),  # only candidate; fails
        ]
    )
    request = ShadowPromotionRequest(
        candidate_policy={"accept_confidence_floor": 0.75},
        max_cost_regression=1.0,
        rollback_trigger=lambda metrics: False,
        baseline_policy={"accept_confidence_floor": 0.95},
        wasted_accept_tolerance=0.1,
    )
    decision = evaluate_shadow_promotion(request, outcomes)
    assert decision.promoted is False
    assert decision.success_yield_delta > 0
    assert decision.wasted_accept_delta > 0.1
    assert any("tolerance ceiling" in reason for reason in decision.reasons)


def test_wasted_rate_within_tolerance_still_promotes() -> None:
    # Same shape as above but the caller accepts the small waste bump;
    # every other gate is green, so the honest throughput gain promotes.
    outcomes = _outcomes(
        [
            (True, 1.0, 10.0, False),
            (True, 0.92, 12.0, False),
            (False, 0.85, 40.0, True),
            (True, 0.93, 11.0, False),
        ]
    )
    request = ShadowPromotionRequest(
        candidate_policy={"accept_confidence_floor": 0.75},
        max_cost_regression=1.0,
        rollback_trigger=lambda metrics: False,
        baseline_policy={"accept_confidence_floor": 0.95},
        wasted_accept_tolerance=0.4,
    )
    decision = evaluate_shadow_promotion(request, outcomes)
    assert decision.success_yield_delta > 0
    assert 0 < decision.wasted_accept_delta <= 0.4
    assert decision.promoted is True


def test_promotion_refused_when_cost_regression_exceeds_threshold() -> None:
    # Baseline routes everything including two slow failures; the
    # candidate drops those failures, so its routed-set mean cost falls.
    # Invert: give the candidate the slow rows via a floor that keeps the
    # expensive ones and drops the cheap successes.
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
        baseline_policy={},
    )
    decision = evaluate_shadow_promotion(request, outcomes)
    # Under the honest semantics this candidate merely rejects two real
    # passes: yield falls, and the cost delta alone must not rescue it.
    assert decision.promoted is False
    assert decision.cost_delta is not None and decision.cost_delta > 0
    assert any(
        "ceiling" in reason or "success_yield" in reason for reason in decision.reasons
    )


def test_promotion_refused_when_rollback_trigger_fires() -> None:
    gate_heavy = [(True, 1.0, 10.0, True), (True, 1.0, 12.0, True)]
    outcomes = _outcomes(gate_heavy)
    request = ShadowPromotionRequest(
        candidate_policy={"accept_confidence_floor": 0.9},
        max_cost_regression=1.0,
        rollback_trigger=lambda metrics: metrics.gate_fail_rate > 0.2,
        baseline_policy={"accept_confidence_floor": 0.99},
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
    assert decision.success_yield_delta == 0.0
    assert decision.cost_delta is None
    assert decision.baseline.decisions == 0


def test_rollback_trigger_receives_candidate_quadrant_metrics() -> None:
    outcomes = _outcomes(
        [
            (True, 1.0, 10.0, False),
            (False, 0.9, 40.0, True),
        ]
    )
    fired_holder: list[PolicyMetrics] = []

    def trigger(metrics: PolicyMetrics) -> bool:
        fired_holder.append(metrics)
        return False

    request = ShadowPromotionRequest(
        candidate_policy={"accept_confidence_floor": 0.5},
        max_cost_regression=1.0,
        rollback_trigger=trigger,
    )
    decision = evaluate_shadow_promotion(request, outcomes)
    assert len(fired_holder) == 1
    assert fired_holder[0] == decision.candidate
    assert fired_holder[0].wasted_accepts == 1
    assert fired_holder[0].successes == 1


RUN_KIND = SHADOW_PROMOTION_RUN_KIND


def test_run_kind_discriminator_value_is_stable() -> None:
    assert RUN_KIND == "shadow_promotion"
