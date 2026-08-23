"""Health-based model eviction (adoption #4) -- pure computation over
attributed `routing_decision_outcomes` samples, plus its gate-5 wiring in
`engine.routing.rules.evaluate`.

No PostgreSQL: outcomes are projected to :class:`HealthSample`s directly.
Covers the mission's named edge cases (no data, all-fail, recovery after
failures), window/threshold mechanics, policy overrides, and the
selection-time behaviour: evicted profiles are hard-eliminated at gate 5
with HEALTH_EVICTED, selection falls through prefer[], a health wipeout
never degrades into the evicted default, and default-off keeps existing
behaviour byte-identical.
"""

from __future__ import annotations

from datetime import UTC, datetime

from engine.contracts.routing_decision_outcome import RoutingDecisionOutcome
from engine.contracts.task import Task
from engine.core.ids import uuid7
from engine.routing.health import (
    DEFAULT_HEALTH_WINDOW_SIZE,
    HealthSample,
    HealthThresholds,
    compute_model_health,
    health_samples_from_outcomes,
    thresholds_from_policy_overrides,
)
from engine.routing.policy import (
    HUMAN_DECISION_TASK,
    PROFILE_DETERMINISTIC_RUNNER,
    PROFILE_GENERAL_IMPLEMENTATION,
    PROFILE_LONGCONTEXT_ECONOMY,
)
from engine.routing.rules import (
    GATE_CAPACITY_AVAILABILITY,
    HEALTH_EVICTED_REASON_CODE,
    evaluate,
)


def _task(**overrides: object) -> Task:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "task_id": uuid7(),
        "tenant_id": uuid7(),
        "project_id": uuid7(),
        "mission_id": uuid7(),
        "graph_id": uuid7(),
        "title": "t",
        "intent": "i",
        "task_class": "implementation",
        "requirement_refs": ["REQ-1"],
        "feature_refs": [],
        "success_criteria": ["c"],
        "expected_write_scope": ["engine/routing"],
        "expected_read_scope": [],
        "blast_radius": "local",
        "risk_class": "low",
        "estimated_effort": "s",
        "autonomy_ceiling": 2,
        "requires_approval": False,
        "status": "CREATED",
        "lock_version": 1,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return Task.model_validate(defaults)


def _outcome(
    *, passed: bool, elapsed_seconds: float | None = None
) -> RoutingDecisionOutcome:
    now = datetime.now(UTC)
    return RoutingDecisionOutcome(
        outcome_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        mission_id=uuid7(),
        task_id=uuid7(),
        route_decision_id=uuid7(),
        task_attempt_id=uuid7(),
        verification_run_id=uuid7(),
        actual_verified_outcome="PASSED" if passed else "FAILED",
        verification_confidence=1.0 if passed else 0.0,
        rework_count=0,
        escalated=False,
        human_intervention_required=False,
        elapsed_seconds=elapsed_seconds,
        context_package_id=uuid7(),
        capability_set=[],
        disclosed_gaps=[],
        created_at=now,
        updated_at=now,
    )


# --- health_samples_from_outcomes ----------------------------------------


def test_unpassed_outcomes_are_failures_and_unattributed_rows_skip() -> None:
    """Failure is `actual_verified_outcome != "PASSED"`; rows whose
    RouteDecision carries no profile id cannot be attributed."""
    samples = health_samples_from_outcomes(
        [
            (_outcome(passed=True), "profile.a"),
            (_outcome(passed=False), "profile.a"),
            (_outcome(passed=False), None),
            (_outcome(passed=True), ""),
        ]
    )
    assert [(s.worker_profile_id, s.failed) for s in samples] == [
        ("profile.a", False),
        ("profile.a", True),
    ]


def test_elapsed_seconds_project_onto_samples() -> None:
    samples = health_samples_from_outcomes(
        [
            (_outcome(passed=True, elapsed_seconds=1.5), "profile.a"),
            (_outcome(passed=False), "profile.b"),
        ]
    )
    assert samples[0].elapsed_seconds == 1.5
    assert samples[1].elapsed_seconds is None


# --- compute_model_health edge cases --------------------------------------


def test_no_data_yields_empty_report_and_no_exclusions() -> None:
    """Absence of evidence is not unhealthiness: an empty history evicts
    nothing."""
    report = compute_model_health([])
    assert report.profiles == {}
    assert report.unhealthy_profiles() == frozenset()


def test_below_min_samples_never_evicts() -> None:
    """An unproven profile is never evicted on suspicion: under the floor,
    even all-fail histories stay healthy."""
    report = compute_model_health(
        [HealthSample("p", failed=True)] * 2,
        thresholds=HealthThresholds(min_samples=3),
    )
    health = report.profiles["p"]
    assert health.sample_count == 2
    assert health.failure_rate == 1.0
    assert health.healthy is True
    assert report.unhealthy_profiles() == frozenset()


def test_all_fail_breaches_threshold_once_floor_is_met() -> None:
    report = compute_model_health([HealthSample("p", failed=True)] * 4)
    health = report.profiles["p"]
    assert (health.sample_count, health.failure_count) == (4, 4)
    assert health.failure_rate == 1.0
    assert health.healthy is False
    assert report.unhealthy_profiles() == frozenset({"p"})


def test_recovery_after_failures_self_clears_the_window() -> None:
    """Expiry is automatic: once successes push the rolling failure rate
    back under the threshold -- partly by ageing old failures out of the
    fixed-size window -- the same profile becomes eligible again with no
    policy edit."""
    history = [HealthSample("p", failed=True)] * 5 + [
        HealthSample("p", failed=False)
    ] * 6

    # Early prefix: 5 fails + 2 passes -> rate ~0.71 breaches 0.6.
    breached = compute_model_health(history[:7])
    assert breached.profiles["p"].sample_count == 7
    assert breached.profiles["p"].failure_rate == 5 / 7
    assert breached.unhealthy_profiles() == frozenset({"p"})

    # Full history: the size-10 window keeps 4 fails + 6 passes -> 0.4.
    recovered = compute_model_health(history)
    recovered_health = recovered.profiles["p"]
    assert recovered_health.sample_count == DEFAULT_HEALTH_WINDOW_SIZE
    assert recovered_health.failure_rate == 4 / 10
    assert recovered.unhealthy_profiles() == frozenset()


def test_window_keeps_only_the_most_recent_samples_per_profile() -> None:
    """Oldest-first input; only the last `window_size` rows per profile
    count: of 8 fails followed by 3 passes, a size-5 window holds
    2 fails + 3 passes."""
    history = [HealthSample("p", failed=True)] * 8 + [
        HealthSample("p", failed=False)
    ] * 3
    report = compute_model_health(history, thresholds=HealthThresholds(window_size=5))
    health = report.profiles["p"]
    assert health.sample_count == 5
    assert health.failure_count == 2
    assert health.failure_rate == 0.4
    assert health.healthy is True


def test_profiles_are_scored_independently() -> None:
    samples = [
        HealthSample("bad", failed=True),
        HealthSample("bad", failed=True),
        HealthSample("bad", failed=True),
        HealthSample("good", failed=False),
        HealthSample("good", failed=True),
        HealthSample("good", failed=False),
    ]
    report = compute_model_health(samples)
    assert report.unhealthy_profiles() == frozenset({"bad"})
    assert report.profiles["good"].mean_elapsed_seconds is None


def test_mean_elapsed_ignores_missing_values() -> None:
    samples = [
        HealthSample("p", failed=False, elapsed_seconds=2.0),
        HealthSample("p", failed=True),
        HealthSample("p", failed=False, elapsed_seconds=4.0),
    ]
    report = compute_model_health(samples)
    assert report.profiles["p"].mean_elapsed_seconds == 3.0


def test_exact_boundary_failure_rate_is_not_a_breach() -> None:
    """>= max_failure_rate stays healthy at exactly the threshold: breach
    means strictly above."""
    report = compute_model_health(
        [HealthSample("p", failed=True)] * 3 + [HealthSample("p", failed=False)] * 2,
        thresholds=HealthThresholds(max_failure_rate=0.6),
    )
    assert report.profiles["p"].failure_rate == 0.6
    assert report.profiles["p"].healthy is True


# --- thresholds_from_policy_overrides -------------------------------------


def test_policy_overrides_map_onto_thresholds_and_ignore_unknown_keys() -> None:
    thresholds = thresholds_from_policy_overrides(
        {
            "health_window_size": "20",
            "health_max_failure_rate": 0.4,
            "health_min_samples": "2",
            "unrelated": "kept-silent",
        }
    )
    assert thresholds == HealthThresholds(
        window_size=20, max_failure_rate=0.4, min_samples=2
    )


def test_none_or_empty_overrides_keep_defaults() -> None:
    assert thresholds_from_policy_overrides(None) == HealthThresholds()
    assert thresholds_from_policy_overrides({}) == HealthThresholds()


# --- selection-time eviction (rules.evaluate) ------------------------------


def test_healthy_history_leaves_selection_untouched() -> None:
    task = _task(task_class="implementation", risk_class="low")
    baseline = evaluate(task)
    with_report = evaluate(
        _task(task_class="implementation", risk_class="low"),
        health_evicted_profiles=frozenset(),
    )
    assert with_report.selected_profile_id == baseline.selected_profile_id
    assert with_report.reason_codes == baseline.reason_codes


def test_unhealthy_profile_is_hard_eliminated_at_gate_five() -> None:
    result = evaluate(
        _task(task_class="implementation", risk_class="low"),
        workload_class="bulk_implementation",
        health_evicted_profiles=frozenset({PROFILE_LONGCONTEXT_ECONOMY}),
    )
    assert result.selected_profile_id == PROFILE_GENERAL_IMPLEMENTATION
    evicted = next(
        c for c in result.candidates if c.profile_id == PROFILE_LONGCONTEXT_ECONOMY
    )
    assert evicted.eliminated_at_gate == GATE_CAPACITY_AVAILABILITY
    assert evicted.gate_results[-1].reason_code == HEALTH_EVICTED_REASON_CODE
    # The decision-level HEALTH_EVICTED:<profiles> code is appended by
    # RouterService when eviction actually fired; rules.evaluate itself
    # records the per-candidate gate result only.
    assert not any(
        code.startswith(f"{HEALTH_EVICTED_REASON_CODE}:")
        for code in result.reason_codes
    )


def test_wipeout_escalates_instead_of_degrading_into_an_evicted_profile() -> None:
    """A health-driven zero-survivor outcome must NOT apply the degraded
    default: degrading into a profile the evidence just evicted would
    defeat the eviction."""
    both = frozenset({PROFILE_LONGCONTEXT_ECONOMY, PROFILE_GENERAL_IMPLEMENTATION})
    result = evaluate(
        _task(task_class="implementation", risk_class="low"),
        workload_class="bulk_implementation",
        routing_environment_class="development",
        allow_degraded_default=True,
        health_evicted_profiles=both,
    )
    assert result.selected_profile_id == HUMAN_DECISION_TASK
    assert "NO_ELIGIBLE_WORKER" in result.reason_codes
    assert "DEGRADED_DEFAULT_APPLIED" not in result.reason_codes


def test_verification_runner_survives_when_economy_is_evicted() -> None:
    """The verification workload's single legal profile is unaffected by
    another band's eviction."""
    result = evaluate(
        _task(task_class="verification"),
        health_evicted_profiles=frozenset({PROFILE_LONGCONTEXT_ECONOMY}),
    )
    assert result.selected_profile_id == PROFILE_DETERMINISTIC_RUNNER
