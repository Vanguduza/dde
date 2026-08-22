"""Chapter 6.2 adoption features (REV 2.0 §6.2 "Cost tiers", §6.1 gate-5
"Degraded-mode default (development only)", §6.3 "Mission-affinity
tie-break") — pure-algorithm tests for `engine.routing.rules` /
`engine.routing.policy`, the same pattern `tests/unit/test_routing_rules.py`
uses for the base pipeline.

Each feature is off by default (`evaluate()`'s signature is unchanged and
every existing call site keeps its exact current behaviour), so every test
here either passes the new optional parameters explicitly or asserts the
default-off invariant.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from engine.contracts.task import Task
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.governance.config import RuntimeFlags, validate_configuration
from engine.routing.policy import (
    CAPABILITY_REPOSITORY,
    CAPABILITY_TESTING,
    HUMAN_DECISION_TASK,
    PROFILE_DETERMINISTIC_RUNNER,
    PROFILE_GENERAL_IMPLEMENTATION,
    PROFILE_LONGCONTEXT_ECONOMY,
    PROFILE_PREMIUM_REASONING,
    WORKLOAD_CLASSES,
    WorkloadPolicy,
    apply_cost_tier,
)
from engine.routing.rules import evaluate


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


# --- Cost-tier reorder (Ch.6.2 cost_tier) -------------------------------


def test_apply_cost_tier_low_reorders_bulk_prefer_order() -> None:
    """low puts the economy profile first; medium keeps the declared order."""
    policy = WORKLOAD_CLASSES["bulk_implementation"]
    low = apply_cost_tier(policy, "low")
    assert low.prefer == (PROFILE_LONGCONTEXT_ECONOMY, PROFILE_GENERAL_IMPLEMENTATION)

    medium = apply_cost_tier(policy, "medium")
    assert medium == policy


def test_apply_cost_tier_high_promotes_premium_when_it_is_a_candidate() -> None:
    """high promotes a premium profile ahead of cheaper profiles *within the
    declared candidate list* — reordering survivors only, never adding
    membership."""
    policy = WorkloadPolicy(
        prefer=(
            PROFILE_LONGCONTEXT_ECONOMY,
            PROFILE_PREMIUM_REASONING,
            PROFILE_GENERAL_IMPLEMENTATION,
        ),
        require=(CAPABILITY_REPOSITORY, CAPABILITY_TESTING),
        max_risk="medium",
    )
    high = apply_cost_tier(policy, "high")
    assert high.prefer == (
        PROFILE_PREMIUM_REASONING,
        PROFILE_LONGCONTEXT_ECONOMY,
        PROFILE_GENERAL_IMPLEMENTATION,
    )
    # Hard-gate fields are untouched.
    assert high.require == policy.require
    assert high.max_risk == policy.max_risk


def test_cost_tier_low_reorders_ranking_without_changing_survivors() -> None:
    """low keeps both economy-band candidates legal but puts the economy
    profile first; every gate result is identical to the untiered run —
    tiers reorder, they never eliminate."""
    task = _task(task_class="implementation", risk_class="low")
    default = evaluate(task)
    low = evaluate(
        _task(task_class="implementation", risk_class="low"), cost_tier="low"
    )
    assert [c.to_json() for c in default.candidates] == [
        c.to_json() for c in low.candidates
    ]
    assert low.reason_codes != default.reason_codes
    assert "COST_TIER:low" in low.reason_codes


@pytest.mark.parametrize("tier", ["bargain", "", "MAXIMUM"])
def test_unknown_cost_tier_is_rejected(tier: str) -> None:
    with pytest.raises(ValueError):
        evaluate(_task(), cost_tier=tier)  # type: ignore[arg-type]


def test_cost_tier_none_keeps_default_behaviour() -> None:
    default = evaluate(_task(task_class="implementation", risk_class="low"))
    explicit = evaluate(
        _task(task_class="implementation", risk_class="low"), cost_tier=None
    )
    assert default.selected_profile_id == explicit.selected_profile_id
    assert default.reason_codes == explicit.reason_codes


# --- Degraded-mode default (dev-only, Ch.6.1 gate-5 note) ----------------


def test_degraded_default_fires_only_on_capacity_failure_in_development() -> None:
    """Gate-5 capacity/availability elimination + dev env + flag on -> degraded
    default. Policy-class eliminations (gate 3) still escalate."""
    task = _task(task_class="implementation", risk_class="low")
    result = evaluate(
        task,
        workload_class="bulk_implementation",
        routing_environment_class="development",
        allow_degraded_default=True,
        capacity_blocked_profiles=frozenset(
            {
                PROFILE_LONGCONTEXT_ECONOMY,
                PROFILE_GENERAL_IMPLEMENTATION,
            }
        ),
    )
    assert result.selected_profile_id == PROFILE_GENERAL_IMPLEMENTATION
    assert "DEGRADED_DEFAULT_APPLIED" in result.reason_codes
    assert "NO_ELIGIBLE_WORKER" not in result.reason_codes


def test_degraded_default_does_not_fire_on_gate3_policy_elimination() -> None:
    """Risk-ceiling gate-3 elimination is governance, not an outage — escalate."""
    task = _task(task_class="implementation", risk_class="critical")
    result = evaluate(
        task,
        workload_class="bulk_implementation",
        routing_environment_class="development",
        allow_degraded_default=True,
    )
    assert result.selected_profile_id == HUMAN_DECISION_TASK
    assert "DEGRADED_DEFAULT_APPLIED" not in result.reason_codes
    assert "NO_ELIGIBLE_WORKER" in result.reason_codes


def test_production_never_applies_the_degraded_default() -> None:
    task = _task(task_class="implementation", risk_class="critical")
    result = evaluate(
        task,
        workload_class="bulk_implementation",
        routing_environment_class="production",
        allow_degraded_default=True,
    )
    assert result.selected_profile_id == HUMAN_DECISION_TASK
    assert "DEGRADED_DEFAULT_APPLIED" not in result.reason_codes
    assert "NO_ELIGIBLE_WORKER" in result.reason_codes


def test_flag_off_escalates_even_in_development() -> None:
    task = _task(task_class="implementation", risk_class="critical")
    result = evaluate(
        task,
        workload_class="bulk_implementation",
        routing_environment_class="development",
        allow_degraded_default=False,
    )
    assert result.selected_profile_id == HUMAN_DECISION_TASK
    assert "NO_ELIGIBLE_WORKER" in result.reason_codes


def test_degraded_default_respects_hard_gate_denial() -> None:
    """A hard-policy denial (gate 0) is never overridden by the degraded
    default — it is not an availability failure but a governance one."""
    result = evaluate(
        _task(task_class="implementation", requires_approval=True),
        workload_class="bulk_implementation",
        routing_environment_class="development",
        allow_degraded_default=True,
    )
    assert result.selected_profile_id == HUMAN_DECISION_TASK
    assert "DEGRADED_DEFAULT_APPLIED" not in result.reason_codes


# --- Mission-affinity tie-break (below declared prefer[]) ---------------


def test_affinity_records_continuity_when_declared_winner_matches_history() -> None:
    """Continuity is recorded only when the declared-order winner is the same
    profile the mission last routed to — affinity never overrides prefer[]."""
    result = evaluate(
        _task(task_class="implementation", risk_class="low"),
        last_selected_profile_id=PROFILE_LONGCONTEXT_ECONOMY,
        enable_mission_affinity=True,
    )
    assert result.selected_profile_id == PROFILE_LONGCONTEXT_ECONOMY
    assert "MISSION_CONTINUITY" in result.reason_codes


def test_affinity_cannot_override_declared_prefer() -> None:
    """The declared prefer[] head wins even when affinity names another
    survivor — continuity is observational, never authority."""
    result = evaluate(
        _task(task_class="implementation", risk_class="low"),
        last_selected_profile_id=PROFILE_GENERAL_IMPLEMENTATION,
        enable_mission_affinity=True,
    )
    assert result.selected_profile_id == PROFILE_LONGCONTEXT_ECONOMY
    assert "MISSION_CONTINUITY" not in result.reason_codes


def test_affinity_does_not_rewrite_recorded_preference_ranks() -> None:
    """The audit trail keeps declared-order ranks regardless of continuity."""
    result = evaluate(
        _task(task_class="implementation", risk_class="low"),
        last_selected_profile_id=PROFILE_GENERAL_IMPLEMENTATION,
        enable_mission_affinity=True,
    )
    ranks = {
        c.profile_id: c.preference_rank
        for c in result.candidates
        if c.preference_rank is not None
    }
    assert ranks[PROFILE_LONGCONTEXT_ECONOMY] == 0
    assert ranks[PROFILE_GENERAL_IMPLEMENTATION] == 1


def test_affinity_disabled_by_default_preserves_current_behaviour() -> None:
    default = evaluate(_task(task_class="implementation", risk_class="low"))
    assert default.selected_profile_id == PROFILE_LONGCONTEXT_ECONOMY
    assert "MISSION_CONTINUITY" not in default.reason_codes


def test_affinity_with_no_history_changes_nothing() -> None:
    result = evaluate(
        _task(task_class="implementation", risk_class="low"),
        last_selected_profile_id=None,
        enable_mission_affinity=True,
    )
    assert result.selected_profile_id == PROFILE_LONGCONTEXT_ECONOMY
    assert "MISSION_CONTINUITY" not in result.reason_codes


# --- Startup validation (Ch.13.7 additive rule) --------------------------


def test_startup_validation_rejects_degraded_default_outside_development() -> None:
    flags = RuntimeFlags(environment_class="production", routing_degraded_default=True)
    with pytest.raises(DdeError):
        validate_configuration(flags)


def test_startup_validation_allows_safe_combinations() -> None:
    dev_on = RuntimeFlags(
        environment_class="development", routing_degraded_default=True
    )
    prod_off = RuntimeFlags(
        environment_class="production", routing_degraded_default=False
    )
    validate_configuration(dev_on)
    validate_configuration(prod_off)


def test_verification_stays_on_deterministic_runner_under_any_tier() -> None:
    """Independence/eligibility gates are upstream of tier reordering: the
    verification workload's single legal profile stays selected under any
    tier."""
    result = evaluate(_task(task_class="verification"), cost_tier="max")
    assert result.selected_profile_id == PROFILE_DETERMINISTIC_RUNNER


# --- OpenRouter model selection (Hermes/DeepSeek harnesses) ---------------


def test_openrouter_selects_strength_matched_model_for_deepseek_harness() -> None:
    """bulk_implementation's strength vector (implementation, batch, corpus)
    matches laguna-s-2.1 (2) over nemotron-ultra (0) for the DeepSeek harness."""
    result = evaluate(
        _task(task_class="implementation", risk_class="low"),
        enable_openrouter_models=True,
    )
    assert "OPENROUTER_MODEL:poolside/laguna-s-2.1:free" in result.reason_codes
    assert "OPENROUTER_CREDENTIAL:deepseek_api_key" in result.reason_codes


def test_openrouter_selects_reasoning_model_for_architectural_workload() -> None:
    """architectural_reasoning (reasoning, architecture, debugging) matches
    nemotron-ultra (3) over glm-5.2 (2) for high-risk tasks routed to
    profile.premium_reasoning (DeepSeek harness)."""
    result = evaluate(
        _task(task_class="implementation", risk_class="high"),
        enable_openrouter_models=True,
    )
    assert (
        "OPENROUTER_MODEL:nvidia/nemotron-3-ultra-550b-a55b:free" in result.reason_codes
    )


def test_openrouter_honours_explicit_model_override() -> None:
    result = evaluate(
        _task(task_class="implementation", risk_class="low"),
        enable_openrouter_models=True,
        openrouter_model_override="google/gemma-4-31b-it:free",
    )
    assert "OPENROUTER_MODEL:google/gemma-4-31b-it:free" in result.reason_codes
    assert "OPENROUTER_OVERRIDE" in result.reason_codes


def test_openrouter_rejects_override_outside_harness_class() -> None:
    """An override naming a valid catalog model that does not serve the
    selected profile's harness class resolves nothing — no fabricated match."""
    result = evaluate(
        _task(task_class="implementation", risk_class="low"),
        enable_openrouter_models=True,
        # north-mini-code serves only the Hermes harness; bulk_implementation
        # on a low-risk task selects longcontext_economy (DeepSeek harness).
        openrouter_model_override="cohere/north-mini-code:free",
    )
    assert not any(code.startswith("OPENROUTER_MODEL:") for code in result.reason_codes)


def test_openrouter_disabled_by_default() -> None:
    result = evaluate(_task(task_class="implementation", risk_class="low"))
    assert not any(code.startswith("OPENROUTER_") for code in result.reason_codes)


def test_openrouter_skips_non_harness_profiles() -> None:
    result = evaluate(
        _task(task_class="verification"),
        enable_openrouter_models=True,
    )
    assert not any(code.startswith("OPENROUTER_MODEL:") for code in result.reason_codes)
