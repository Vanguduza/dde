"""Chapter 6.1 deterministic routing pipeline — pure algorithm tests
(`engine.routing.rules`), the same "test the pure module directly"
pattern `tests/unit/test_context_fusion.py`/`test_planning.py` use for
their chapters' pure algorithms."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.contracts.task import Task
from engine.core.ids import uuid7
from engine.routing.policy import (
    HUMAN_DECISION_TASK,
    PROFILE_DETERMINISTIC_RUNNER,
    PROFILE_GENERAL_IMPLEMENTATION,
    PROFILE_LONGCONTEXT_ECONOMY,
    PROFILE_PREMIUM_REASONING,
    WORKLOAD_CLASSES,
)
from engine.routing.registry import PROFILES
from engine.routing.rules import _evaluate_candidate, classify_workload, evaluate


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


def test_classify_workload_verification_task_class() -> None:
    assert classify_workload(_task(task_class="verification")) == "verification"


def test_classify_workload_high_risk_is_architectural_reasoning() -> None:
    assert (
        classify_workload(_task(task_class="implementation", risk_class="high"))
        == "architectural_reasoning"
    )
    assert (
        classify_workload(_task(task_class="implementation", risk_class="critical"))
        == "architectural_reasoning"
    )


def test_classify_workload_defaults_to_bulk_implementation() -> None:
    assert (
        classify_workload(_task(task_class="implementation", risk_class="low"))
        == "bulk_implementation"
    )
    assert (
        classify_workload(_task(task_class="implementation", risk_class="medium"))
        == "bulk_implementation"
    )


def test_evaluate_selects_first_preferred_profile_for_bulk_implementation() -> None:
    result = evaluate(_task(task_class="implementation", risk_class="low"))
    assert result.workload_class == "bulk_implementation"
    assert result.selected_profile_id == PROFILE_LONGCONTEXT_ECONOMY
    assert (
        result.required_capabilities == WORKLOAD_CLASSES["bulk_implementation"].require
    )
    assert f"SELECTED:{PROFILE_LONGCONTEXT_ECONOMY}" in result.reason_codes
    assert result.fallback_plan == (
        {"profile_id": PROFILE_GENERAL_IMPLEMENTATION, "preference_rank": 1},
    )


def test_evaluate_two_genuinely_different_inputs_produce_two_different_outcomes() -> (
    None
):
    """The core acceptance proof: a low-risk implementation task and a
    high-risk implementation task are real, different `Task` rows and
    route to genuinely different worker profiles under the same
    deterministic policy — not a single hardcoded branch."""
    low_risk = evaluate(_task(task_class="implementation", risk_class="low"))
    high_risk = evaluate(_task(task_class="implementation", risk_class="high"))

    assert low_risk.workload_class != high_risk.workload_class
    assert low_risk.selected_profile_id != high_risk.selected_profile_id
    assert low_risk.selected_profile_id == PROFILE_LONGCONTEXT_ECONOMY
    assert high_risk.selected_profile_id == PROFILE_PREMIUM_REASONING


def test_evaluate_selects_deterministic_runner_for_verification() -> None:
    result = evaluate(_task(task_class="verification"))
    assert result.workload_class == "verification"
    assert result.selected_profile_id == PROFILE_DETERMINISTIC_RUNNER


def test_evaluate_generator_independence_excludes_the_generating_profile() -> None:
    """Chapter 6.2's verification `forbid` clause / Chapter 11.4: a profile
    that produced the change under test cannot also verify it."""
    result = evaluate(
        _task(task_class="verification"),
        previous_generator_profile_id=PROFILE_DETERMINISTIC_RUNNER,
    )
    generator_candidate = next(
        candidate
        for candidate in result.candidates
        if candidate.profile_id == PROFILE_DETERMINISTIC_RUNNER
    )
    assert generator_candidate.eliminated_at_gate == 3
    assert generator_candidate.gate_results[-1].reason_code == (
        "GENERATOR_INDEPENDENCE_VIOLATION"
    )
    # No other profile is `prefer`-certified for `verification`, so the
    # decision genuinely has no eligible worker left.
    assert result.selected_profile_id == HUMAN_DECISION_TASK
    assert "NO_ELIGIBLE_WORKER" in result.reason_codes


def test_evaluate_hard_policy_gate_clears_when_approval_is_satisfied() -> None:
    result = evaluate(
        _task(task_class="implementation", requires_approval=True),
        approval_satisfied=True,
    )
    assert "HARD_GATE_APPROVAL_REQUIRED" not in result.reason_codes
    assert result.selected_profile_id != HUMAN_DECISION_TASK


def test_evaluate_records_every_registered_profile_as_a_candidate() -> None:
    result = evaluate(_task(task_class="implementation", risk_class="low"))
    assert {candidate.profile_id for candidate in result.candidates} == set(PROFILES)
    assert len(result.candidates) == len(PROFILES)


def test_evaluate_risk_floor_eliminates_every_candidate_when_unmet() -> None:
    """A task overridden into `architectural_reasoning` below its declared
    `min_risk: high` floor has no legal candidate — the hard-gate rule
    (6.1: "no economic score can compensate") is structurally enforced,
    not merely unobserved under normal classifier-driven use."""
    result = evaluate(
        _task(task_class="implementation", risk_class="low"),
        workload_class="architectural_reasoning",
    )
    assert result.selected_profile_id == HUMAN_DECISION_TASK
    reasoning_candidate = next(
        candidate
        for candidate in result.candidates
        if candidate.profile_id == PROFILE_PREMIUM_REASONING
    )
    assert reasoning_candidate.eliminated_at_gate == 3
    assert (
        reasoning_candidate.gate_results[-1].reason_code == "RISK_BELOW_WORKLOAD_FLOOR"
    )


def test_evaluate_risk_ceiling_eliminates_every_candidate_when_exceeded() -> None:
    result = evaluate(
        _task(task_class="implementation", risk_class="critical"),
        workload_class="bulk_implementation",
    )
    assert result.selected_profile_id == HUMAN_DECISION_TASK
    economy_candidate = next(
        candidate
        for candidate in result.candidates
        if candidate.profile_id == PROFILE_LONGCONTEXT_ECONOMY
    )
    assert economy_candidate.eliminated_at_gate == 3
    assert (
        economy_candidate.gate_results[-1].reason_code == "RISK_ABOVE_WORKLOAD_CEILING"
    )


def test_evaluate_visual_analysis_selects_only_the_capability_matching_profile() -> (
    None
):
    result = evaluate(
        _task(task_class="implementation", risk_class="low"),
        workload_class="visual_analysis",
    )
    assert result.selected_profile_id == "profile.vision"
    non_vision = [
        candidate
        for candidate in result.candidates
        if candidate.profile_id != "profile.vision"
    ]
    assert all(candidate.eliminated_at_gate is not None for candidate in non_vision)


def test_candidate_eliminated_at_environment_gate_when_env_incompatible() -> None:
    """Chapter 6.1 gate 4, isolated: a profile that clears capability
    requirements and workload eligibility but does not support the
    required environment class is eliminated there specifically — not
    conflated with the gate 1 capability check. No registered Stage 1
    profile is capability-eligible-but-environment-incompatible for any
    reachable workload class today, so this exercises `_evaluate_candidate`
    directly rather than leaving Chapter 6.1's fifth gate untested."""
    gate_results = _evaluate_candidate(
        PROFILE_LONGCONTEXT_ECONOMY,
        required_capabilities=WORKLOAD_CLASSES["bulk_implementation"].require,
        required_environment_class="container-gpu",
        risk_class="low",
        hard_gate_denied=False,
        prefer=WORKLOAD_CLASSES["bulk_implementation"].prefer,
        forbid_generator=False,
        min_risk=None,
        max_risk=None,
        previous_generator_profile_id=None,
    )
    assert gate_results[-1].reason_code == "ENVIRONMENT_INCOMPATIBLE"
    assert gate_results[-1].gate == 4


def test_evaluate_is_deterministic_across_calls() -> None:
    task = _task(task_class="implementation", risk_class="low")
    first = evaluate(task)
    second = evaluate(task)
    assert first.selected_profile_id == second.selected_profile_id
    assert [c.to_json() for c in first.candidates] == [
        c.to_json() for c in second.candidates
    ]
    assert first.reason_codes == second.reason_codes


def test_evaluate_production_does_not_select_a_stale_profile() -> None:
    """Chapter 8.5: STALE is selectable in development and blocked in
    production routing. The next eligible certified preferred profile is
    selected rather than silently using the stale hash.
    """
    production = evaluate(
        _task(task_class="implementation", risk_class="low"),
        certification_statuses={
            PROFILE_LONGCONTEXT_ECONOMY: "STALE",
            PROFILE_GENERAL_IMPLEMENTATION: "CERTIFIED",
        },
        routing_environment_class="production",
    )
    assert production.selected_profile_id == PROFILE_GENERAL_IMPLEMENTATION
    stale_candidate = next(
        candidate
        for candidate in production.candidates
        if candidate.profile_id == PROFILE_LONGCONTEXT_ECONOMY
    )
    assert stale_candidate.eliminated_at_gate == 3
    assert stale_candidate.gate_results[-1].reason_code == "PROFILE_STALE"

    development = evaluate(
        _task(task_class="implementation", risk_class="low"),
        certification_statuses={
            PROFILE_LONGCONTEXT_ECONOMY: "STALE",
            PROFILE_GENERAL_IMPLEMENTATION: "CERTIFIED",
        },
        routing_environment_class="development",
    )
    assert development.selected_profile_id == PROFILE_LONGCONTEXT_ECONOMY
