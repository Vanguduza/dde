"""Chapter 6.2 adoption features (REV 2.0 §6.2 "Cost tiers", §6.1 gate-5
"Degraded-mode default (development only)", §6.3 "Mission-affinity
tie-break") — pure-algorithm tests for `engine.routing.rules` /
`engine.routing.policy`, the same pattern `tests/unit/test_routing_rules.py`
uses for the base pipeline.

Each feature is off by default (`evaluate()`'s existing parameters keep
their exact current behaviour), so every test here either passes the new
optional parameters explicitly or asserts the default-off invariant.
Model selection is provider-agnostic: an operator mode ("off" | "auto" |
"fixed", with `model_fixed_id`/`model_fixed_provider` pinning any declared
provider) resolves to a `ModelSelectionDirective` via
`engine.routing.registry.resolve_model_selection` and only annotates
surviving candidates downstream of every hard gate — it never changes a
gate outcome or makes a live provider call.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from engine.contracts.task import Task
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.governance.config import (
    MODEL_PROVIDERS as GOVERNANCE_MODEL_PROVIDERS,
)
from engine.governance.config import (
    RuntimeFlags,
    validate_configuration,
)
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
from engine.routing.registry import (
    MODEL_PROVIDERS as REGISTRY_MODEL_PROVIDERS,
)
from engine.routing.registry import (
    OPENROUTER_FREE_MODELS,
    ModelSelectionDirective,
    resolve_model_selection,
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
        evaluate(_task(), cost_tier=tier)


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


# --- Model selection (provider-agnostic; Appendix A harnesses) ------------


def test_auto_mode_strength_matches_the_declared_catalog() -> None:
    """auto enables unpinned selection: bulk_implementation's strength vector
    (implementation, batch, corpus) matches laguna-s-2.1 (2) over
    nemotron-ultra (0) for the DeepSeek-harness profile that wins routing."""
    directive = resolve_model_selection("auto", None)
    result = evaluate(
        _task(task_class="implementation", risk_class="low"),
        model_selection=directive,
    )
    assert "OPENROUTER_MODEL:poolside/laguna-s-2.1:free" in result.reason_codes
    assert "OPENROUTER_CREDENTIAL:deepseek_api_key" in result.reason_codes


def test_auto_mode_strength_matches_reasoning_for_architectural_workload() -> None:
    """architectural_reasoning (reasoning, architecture, debugging) matches
    nemotron-ultra (3) over glm-5.2 (2) for high-risk tasks routed to
    profile.premium_reasoning (DeepSeek harness)."""
    directive = resolve_model_selection("auto", None)
    result = evaluate(
        _task(task_class="implementation", risk_class="high"),
        model_selection=directive,
    )
    assert (
        "OPENROUTER_MODEL:nvidia/nemotron-3-ultra-550b-a55b:free" in result.reason_codes
    )


def test_off_directive_and_none_keep_default_behaviour() -> None:
    """mode="off" resolves to a disabled directive that annotates nothing,
    exactly like passing no directive at all."""
    task = _task(task_class="implementation", risk_class="low")
    off = evaluate(task, model_selection=resolve_model_selection("off", None))
    none = evaluate(task, model_selection=None)
    default = evaluate(task)
    assert off.selected_profile_id == none.selected_profile_id
    assert off.reason_codes == none.reason_codes == default.reason_codes
    assert not any(code.startswith("OPENROUTER_") for code in off.reason_codes)


def test_auto_mode_skips_non_harness_profiles() -> None:
    """deterministic_runner has no harness class, so even an enabled
    selection records no model annotation for verification workloads."""
    result = evaluate(
        _task(task_class="verification"),
        model_selection=resolve_model_selection("auto", None),
    )
    assert not any(code.startswith("OPENROUTER_MODEL:") for code in result.reason_codes)


def test_fixed_mode_pins_model_provider_and_declared_credential() -> None:
    """A pin is an operator instruction: recorded as PINNED_* codes with the
    provider's declared credential tier, never a strength match."""
    directive = resolve_model_selection("fixed", "google/gemma-4-31b-it:free")
    assert directive.pinned_provider == "openrouter"
    result = evaluate(
        _task(task_class="implementation", risk_class="low"),
        model_selection=directive,
    )
    assert "PINNED_MODEL:google/gemma-4-31b-it:free" in result.reason_codes
    assert "PINNED_PROVIDER:openrouter" in result.reason_codes
    assert "PINNED_CREDENTIAL:deepseek_api_key" in result.reason_codes


def test_fixed_mode_pin_does_not_change_gate_outcomes_or_survivors() -> None:
    """Selection only annotates the surviving profile downstream of every
    hard gate — candidates and selection are identical with and without a
    pin; only the appended PINNED_* reason codes differ."""
    task = _task(task_class="implementation", risk_class="low")
    plain = evaluate(task, model_selection=resolve_model_selection("auto", None))
    pinned = evaluate(
        task,
        model_selection=resolve_model_selection(
            "fixed", "google/gemma-4-31b-it:free", "openrouter"
        ),
    )
    assert [c.to_json() for c in pinned.candidates] == [
        c.to_json() for c in plain.candidates
    ]
    assert pinned.selected_profile_id == plain.selected_profile_id
    assert pinned.fallback_plan == plain.fallback_plan


def test_governance_and_registry_stay_aligned_on_providers() -> None:
    """Governance restates the provider ids because it must not import
    engine.routing; this assertion is the declared alignment check."""
    assert GOVERNANCE_MODEL_PROVIDERS == tuple(REGISTRY_MODEL_PROVIDERS)


# --- Startup validation (Ch.13.7 model-mode rules) ------------------------


def test_governance_accepts_model_modes_in_every_environment_class() -> None:
    """Model choice only reorders candidates downstream of every hard gate,
    so every legal mode is legal everywhere; mode=fixed requires both pin
    fields."""
    validate_configuration(RuntimeFlags(environment_class="development"))
    validate_configuration(
        RuntimeFlags(environment_class="production", model_mode="off")
    )
    validate_configuration(
        RuntimeFlags(environment_class="production", model_mode="auto")
    )
    validate_configuration(
        RuntimeFlags(
            environment_class="production",
            model_mode="fixed",
            model_fixed_id="google/gemma-4-31b-it:free",
            model_fixed_provider="openrouter",
        )
    )
    validate_configuration(
        RuntimeFlags(
            environment_class="development",
            model_mode="fixed",
            model_fixed_id="deepseek/deepseek-chat",
            model_fixed_provider="deepseek",
        )
    )


def test_governance_rejects_unknown_model_mode() -> None:
    flags = RuntimeFlags(model_mode="random")
    with pytest.raises(DdeError):
        validate_configuration(flags)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"model_fixed_id": "google/gemma-4-31b-it:free"},
        {"model_fixed_provider": "openrouter"},
    ],
)
def test_governance_fixed_mode_requires_both_pin_fields(kwargs: dict[str, str]) -> None:
    flags = RuntimeFlags(model_mode="fixed", **kwargs)  # type: ignore[arg-type]
    with pytest.raises(DdeError):
        validate_configuration(flags)


def test_governance_rejects_undeclared_fixed_provider() -> None:
    flags = RuntimeFlags(
        model_mode="fixed",
        model_fixed_id="vendor/model",
        model_fixed_provider="not-a-provider",
    )
    with pytest.raises(DdeError):
        validate_configuration(flags)


@pytest.mark.parametrize("model_mode", ["off", "auto"])
def test_governance_rejects_pins_contradicting_off_or_auto(model_mode: str) -> None:
    """A pin attached to anything but mode=fixed is a contradiction, not an
    override — either field alone is enough to reject."""
    with pytest.raises(DdeError):
        validate_configuration(
            RuntimeFlags(
                model_mode=model_mode,
                model_fixed_id="google/gemma-4-31b-it:free",
            )
        )
    with pytest.raises(DdeError):
        validate_configuration(
            RuntimeFlags(
                model_mode=model_mode,
                model_fixed_provider="openrouter",
            )
        )


# --- Directive resolution (registry.resolve_model_selection) --------------


def test_resolve_model_selection_maps_all_three_modes() -> None:
    assert resolve_model_selection("off", None) == ModelSelectionDirective(
        enabled=False
    )
    assert resolve_model_selection("auto", None) == ModelSelectionDirective(
        enabled=True
    )
    # Two-argument fixed pins default the provider to openrouter.
    assert resolve_model_selection("fixed", "google/gemma-4-31b-it:free") == (
        ModelSelectionDirective(
            enabled=True,
            pinned_model_id="google/gemma-4-31b-it:free",
            pinned_provider="openrouter",
        )
    )


def test_resolve_model_selection_rejects_unknown_mode_and_empty_fixed_id() -> None:
    with pytest.raises(ValueError, match="unknown model-selection mode"):
        resolve_model_selection("random", None)
    with pytest.raises(ValueError, match="requires a fixed_model_id"):
        resolve_model_selection("fixed", "")
    with pytest.raises(ValueError, match="requires a fixed_model_id"):
        resolve_model_selection("fixed", None)


def test_resolve_model_selection_rejects_undeclared_provider() -> None:
    with pytest.raises(ValueError, match="not a declared"):
        resolve_model_selection("fixed", "vendor/model", "not-a-provider")


def test_openrouter_ids_are_not_whitelisted_to_the_free_catalog() -> None:
    """OPENROUTER_FREE_MODELS is only the strength-match subset of the
    catalog, never a whitelist: any well-formed <vendor>/<model> id resolves
    for provider openrouter, including ids absent from the free list."""
    catalog_ids = {spec.model_id for spec in OPENROUTER_FREE_MODELS}
    unpinned = "paid/vendor-only-model:beta"
    assert "/" in unpinned
    assert unpinned not in catalog_ids
    directive = resolve_model_selection("fixed", unpinned)
    assert directive.enabled
    assert directive.pinned_model_id == unpinned
    assert directive.pinned_provider == "openrouter"


@pytest.mark.parametrize("provider", ["deepseek", "anthropic"])
def test_non_openrouter_declared_providers_take_their_own_ids(provider: str) -> None:
    """Every declared provider accepts ids as-is; only openrouter enforces
    the well-formed <vendor>/<model> shape."""
    directive = resolve_model_selection("fixed", f"{provider}-internal-model", provider)
    assert directive.enabled
    assert directive.pinned_provider == provider
    assert directive.pinned_model_id == f"{provider}-internal-model"


def test_openrouter_fixed_id_must_be_well_formed() -> None:
    """The one openrouter-side shape rule: a bare name is not a routable
    OpenRouter id (<vendor>/<model>)."""
    with pytest.raises(ValueError, match="well-formed"):
        resolve_model_selection("fixed", "bare-model-name")
