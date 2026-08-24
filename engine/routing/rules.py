"""Chapter 6.1's routing pipeline, implemented exactly to its stated
precedence: gates 0-5 are hard gates ("a candidate that fails any of gates
0-5 is removed, not penalised. No economic score can compensate...");
gates 6-9 (§6.6-6.9: performance estimate, economic score, route critic,
escalation) "only ever reorder legal candidates". Chapter 6.5's real
outcome telemetry now exists (`engine.telemetry`, DDE-035), but no real
`predicted_success`/cost prediction is produced from it yet, and no
Route Critic runs (triggered-only, §6.6, deferred until a real prediction
exists to threshold against -- see
`docs/truth/edr/EDR-0005-routing-telemetry-partial-implementation.md`) —
the one real, declared-policy signal available for ranking survivors is
Chapter 6.2's own `prefer[]` ordering, so that is gates 6-7's entire
Stage 1 implementation: it is the deterministic tie-break, not a
placeholder for one.

**Gate numbering vs. evaluation order.** Chapter 6.1 lists gate 1
(capability requirements) before gate 2 (workload classification), but
6.2's own policy table nests `require[]` *inside* each `workload_classes`
entry — required capabilities are a function of the assigned workload
class, not an independent, prior computation. This module therefore
classifies the workload first (a pure function of real `Task` fields,
`task_class` and `risk_class` — the only two Chapter 6 cites as gate
inputs: `min_risk`/`max_risk` bounds in 6.2's example, and Chapter 5.9's
`risk_class >= high` threshold used the same way here for
`architectural_reasoning`), then reads `required_capabilities` and
`required_environment_class` off that class's declared policy, then
evaluates every registered profile against gates 0, 1, 3, 4, 5 in that
literal numeric order. Gate 2 itself has no per-candidate elimination —
it is the classification step that determines which policy row gates 1
and 3 read from, exactly as its position between gates 1 and 3 implies
("WORKER ELIGIBILITY — certified profiles that can satisfy 1+2").

`visual_analysis` is not selected by `classify_workload` from Task fields
alone (no keyword heuristic); callers with a real modality signal pass
`workload_class="visual_analysis"` to `evaluate` directly (DDE-044 makes
`visual_diff` evidence executable; DDE-068 owns VLM critique).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from engine.contracts.task import Task
from engine.routing.policy import (
    HUMAN_DECISION_TASK,
    RISK_ORDER,
    WORKLOAD_CLASSES,
    apply_cost_tier,
)
from engine.routing.registry import (
    MODEL_PROVIDERS,
    PROFILE_HARNESS_CLASS,
    PROFILES,
    ModelSelectionDirective,
    required_environment_class,
    resolve_openrouter_model,
)

GATE_HARD_POLICY = 0
GATE_CAPABILITY_REQUIREMENTS = 1
GATE_WORKER_ELIGIBILITY = 3
GATE_ENVIRONMENT_COMPATIBILITY = 4
GATE_CAPACITY_AVAILABILITY = 5

#: Health-based eviction (adoption #4): a profile whose rolling failure
#: rate over recorded `routing_decision_outcomes` breaches its threshold
#: is removed at Chapter 6.1's gate 5 -- hard-elimination semantics,
#: "removed, not penalised". Expiry is automatic: once recent outcomes no
#: longer breach the threshold, the window clears itself and the profile
#: becomes eligible again without any policy edit.
HEALTH_EVICTED_REASON_CODE = "HEALTH_EVICTED"


#: Chapter 6.1 gate-5 note's development-only degraded default: the
#: general-implementation profile is the declared fallback when no legal
#: candidate survives in a non-production environment class and the caller
#: explicitly opted in. Membership-checked against `PROFILES` before use.
DEGRADED_DEFAULT_PROFILE_ID = "profile.general_implementation"


@dataclass(frozen=True)
class GateResult:
    gate: int
    gate_name: str
    passed: bool
    reason_code: str

    def to_json(self) -> dict[str, object]:
        return {
            "gate": self.gate,
            "gate_name": self.gate_name,
            "passed": self.passed,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True)
class CandidateEvaluation:
    profile_id: str
    gate_results: tuple[GateResult, ...]
    eliminated_at_gate: int | None
    preference_rank: int | None

    def to_json(self) -> dict[str, object]:
        scores: dict[str, object] = (
            {}
            if self.preference_rank is None
            else {"preference_rank": self.preference_rank}
        )
        return {
            "profile_id": self.profile_id,
            "gate_results": [result.to_json() for result in self.gate_results],
            "eliminated_at_gate": self.eliminated_at_gate,
            "scores": scores,
        }


@dataclass(frozen=True)
class RoutingResult:
    workload_class: str
    required_capabilities: tuple[str, ...]
    required_environment_class: str
    candidates: tuple[CandidateEvaluation, ...]
    selected_profile_id: str
    reason_codes: tuple[str, ...]
    fallback_plan: tuple[dict[str, object], ...]


def classify_workload(task: Task) -> str:
    """Chapter 6.1 gate 2, from real, already-persisted `Task` fields only
    (Chapter 4.2). `blast_radius` is deliberately not consulted:
    `workload_classes` in Chapter 6.2's example keys its risk bounds
    (`min_risk`/`max_risk`) on `risk_class` alone."""
    if task.task_class == "verification":
        return "verification"
    if RISK_ORDER[task.risk_class] >= RISK_ORDER["high"]:
        return "architectural_reasoning"
    return "bulk_implementation"


CAPACITY_UNAVAILABLE_REASONS = frozenset(
    {
        "CAPACITY_EXHAUSTED",
        "QUOTA_EXCEEDED",
        "CONCURRENCY_LIMIT",
        "BUDGET_HEADROOM_INSUFFICIENT",
        "WORKER_UNAVAILABLE",
    }
)


def _evaluate_candidate(
    profile_id: str,
    *,
    required_capabilities: tuple[str, ...],
    required_environment_class: str,
    risk_class: str,
    hard_gate_denied: bool,
    prefer: tuple[str, ...],
    forbid_generator: bool,
    min_risk: str | None,
    max_risk: str | None,
    previous_generator_profile_id: str | None,
    certification_status: str | None = None,
    allow_stale: bool = True,
    capacity_blocked: bool = False,
    health_evicted: bool = False,
) -> tuple[GateResult, ...]:
    profile = PROFILES[profile_id]
    results: list[GateResult] = []

    if hard_gate_denied:
        results.append(
            GateResult(
                GATE_HARD_POLICY, "hard_policy", False, "HARD_GATE_APPROVAL_REQUIRED"
            )
        )
        return tuple(results)
    results.append(GateResult(GATE_HARD_POLICY, "hard_policy", True, "HARD_GATE_CLEAR"))

    missing_capabilities = [
        capability
        for capability in required_capabilities
        if capability not in profile.capabilities
    ]
    if missing_capabilities:
        results.append(
            GateResult(
                GATE_CAPABILITY_REQUIREMENTS,
                "capability_requirements",
                False,
                "CAPABILITY_GAP",
            )
        )
        return tuple(results)
    results.append(
        GateResult(
            GATE_CAPABILITY_REQUIREMENTS,
            "capability_requirements",
            True,
            "CAPABILITY_FIT",
        )
    )

    if certification_status is not None:
        certified = certification_status == "CERTIFIED" or (
            certification_status == "STALE" and allow_stale
        )
        if not certified:
            results.append(
                GateResult(
                    GATE_WORKER_ELIGIBILITY,
                    "worker_eligibility",
                    False,
                    "PROFILE_STALE",
                )
            )
            return tuple(results)

    if profile_id not in prefer:
        results.append(
            GateResult(
                GATE_WORKER_ELIGIBILITY,
                "worker_eligibility",
                False,
                "NOT_CERTIFIED_FOR_WORKLOAD",
            )
        )
        return tuple(results)
    if forbid_generator and previous_generator_profile_id == profile_id:
        results.append(
            GateResult(
                GATE_WORKER_ELIGIBILITY,
                "worker_eligibility",
                False,
                "GENERATOR_INDEPENDENCE_VIOLATION",
            )
        )
        return tuple(results)
    if min_risk is not None and RISK_ORDER[risk_class] < RISK_ORDER[min_risk]:
        results.append(
            GateResult(
                GATE_WORKER_ELIGIBILITY,
                "worker_eligibility",
                False,
                "RISK_BELOW_WORKLOAD_FLOOR",
            )
        )
        return tuple(results)
    if max_risk is not None and RISK_ORDER[risk_class] > RISK_ORDER[max_risk]:
        results.append(
            GateResult(
                GATE_WORKER_ELIGIBILITY,
                "worker_eligibility",
                False,
                "RISK_ABOVE_WORKLOAD_CEILING",
            )
        )
        return tuple(results)
    results.append(
        GateResult(
            GATE_WORKER_ELIGIBILITY, "worker_eligibility", True, "POLICY_PREFERRED"
        )
    )

    if required_environment_class not in profile.environment_classes:
        results.append(
            GateResult(
                GATE_ENVIRONMENT_COMPATIBILITY,
                "environment_compatibility",
                False,
                "ENVIRONMENT_INCOMPATIBLE",
            )
        )
        return tuple(results)
    results.append(
        GateResult(
            GATE_ENVIRONMENT_COMPATIBILITY,
            "environment_compatibility",
            True,
            "ENVIRONMENT_COMPATIBLE",
        )
    )

    # Gate 5: pass-through when no signal exists (Chapter 8 Worker Manager,
    # DDE-011). Callers may supply `capacity_blocked_profiles` to exercise
    # real capacity/availability eliminations in tests or when telemetry
    # arrives — never fabricated health checks in production paths.
    if capacity_blocked:
        results.append(
            GateResult(
                GATE_CAPACITY_AVAILABILITY,
                "capacity_availability",
                False,
                "CAPACITY_EXHAUSTED",
            )
        )
        return tuple(results)
    if health_evicted:
        results.append(
            GateResult(
                GATE_CAPACITY_AVAILABILITY,
                "capacity_availability",
                False,
                HEALTH_EVICTED_REASON_CODE,
            )
        )
        return tuple(results)
    results.append(
        GateResult(
            GATE_CAPACITY_AVAILABILITY,
            "capacity_availability",
            True,
            "AVAILABILITY_NOT_TRACKED",
        )
    )
    return tuple(results)


def evaluate(
    task: Task,
    *,
    workload_class: str | None = None,
    previous_generator_profile_id: str | None = None,
    certification_statuses: Mapping[str, str] | None = None,
    routing_environment_class: str = "development",
    approval_satisfied: bool = False,
    cost_tier: str | None = None,
    allow_degraded_default: bool = False,
    enable_mission_affinity: bool = False,
    last_selected_profile_id: str | None = None,
    capacity_blocked_profiles: frozenset[str] | None = None,
    health_evicted_profiles: frozenset[str] | None = None,
    model_selection: ModelSelectionDirective | None = None,
) -> RoutingResult:
    """Run every registered profile through Chapter 6.1's gates 0-5 for
    `task`, then rank survivors by Chapter 6.2's declared `prefer[]` order
    (gates 6-7's Stage 1 tie-break) and select the top-ranked one. Returns
    a real `HUMAN_DECISION_TASK` escalation, never an exception, when zero
    candidates survive — Chapter 6.1 gate 9 treats escalation as a normal,
    recordable routing outcome, not a failure.

    Additive Chapter 6 adoption parameters, all default-off so existing
    callers keep byte-identical behaviour:

    - `cost_tier` (§6.2): reorders the declared `prefer[]` before ranking;
      never changes gate outcomes (survivor-preserving).
    - `allow_degraded_default` (gate-5 availability note): when zero
      candidates survive a *capacity/availability-class* failure in the
      `development` environment class, select the declared degraded default
      instead of escalating — mirroring §6.1's "a request never fails
      because of a routing problem" for non-production only. A gate-0
      hard-policy denial is governance, not an outage, and still escalates.
    - `enable_mission_affinity` + `last_selected_profile_id` (§6.3):
      records mission continuity when the declared-order winner matches the
      last-selected profile; declared `prefer[]` always outranks affinity and
      affinity never reorders survivors.
    - `capacity_blocked_profiles`: optional gate-5 capacity signal for tests
      or future Worker Manager integration.
    - `health_evicted_profiles` (adoption #4): profiles whose recorded
      outcome health breached its threshold. Each is hard-eliminated at
      gate 5 with a `HEALTH_EVICTED` reason code and the selection falls
      through to the next `prefer[]` entry -- the policy table itself is
      the fallback chain, walked once in declared order, never looping.
    - `model_selection` (§6.2/6.3, Appendix A harnesses; provider-agnostic):
      a resolved `ModelSelectionDirective` from
      `engine.routing.registry.resolve_model_selection`. Pinned (fixed) mode
      records `PINNED_MODEL/PINNED_PROVIDER/PINNED_CREDENTIAL` reason codes
      for the selected profile's harness class and skips strength matching;
      auto (unpinned) strength-matches the OpenRouter free catalog exactly as
      before. Either way the selection only annotates survivors with declared
      metadata — no live provider call is made and gate outcomes are never
      changed (adapters stay fail-closed pending broker credentials,
      EDR-0001 Path B).
    """
    resolved_workload_class = workload_class or classify_workload(task)
    policy = WORKLOAD_CLASSES[resolved_workload_class]
    tiered_policy = (
        apply_cost_tier(policy, cost_tier) if cost_tier is not None else policy
    )
    required_capabilities = tiered_policy.require
    environment_class = required_environment_class(required_capabilities)
    hard_gate_denied = task.requires_approval and not approval_satisfied

    evaluations: list[CandidateEvaluation] = []
    survivor_ids: list[str] = []
    allow_stale = routing_environment_class == "development"
    blocked = capacity_blocked_profiles or frozenset()
    evicted = health_evicted_profiles or frozenset()
    for profile_id in sorted(PROFILES):
        status = (
            None
            if certification_statuses is None
            else certification_statuses.get(profile_id, "ABSENT")
        )
        gate_results = _evaluate_candidate(
            profile_id,
            required_capabilities=required_capabilities,
            required_environment_class=environment_class,
            risk_class=task.risk_class,
            hard_gate_denied=hard_gate_denied,
            prefer=tiered_policy.prefer,
            forbid_generator=tiered_policy.forbid_generator,
            min_risk=tiered_policy.min_risk,
            max_risk=tiered_policy.max_risk,
            previous_generator_profile_id=previous_generator_profile_id,
            certification_status=status,
            allow_stale=allow_stale,
            capacity_blocked=profile_id in blocked,
            health_evicted=profile_id in evicted,
        )
        eliminated_at = None if gate_results[-1].passed else gate_results[-1].gate
        if eliminated_at is None:
            survivor_ids.append(profile_id)
        evaluations.append(
            CandidateEvaluation(
                profile_id=profile_id,
                gate_results=gate_results,
                eliminated_at_gate=eliminated_at,
                preference_rank=None,
            )
        )

    ranked_survivors = sorted(survivor_ids, key=tiered_policy.prefer.index)
    reason_codes: list[str] = [f"WORKLOAD_CLASSIFIED:{resolved_workload_class}"]
    if cost_tier is not None:
        reason_codes.append(f"COST_TIER:{cost_tier}")

    preferred_first = list(ranked_survivors)
    capacity_class_zero_survivors = not survivor_ids and any(
        evaluation.eliminated_at_gate == GATE_CAPACITY_AVAILABILITY
        and evaluation.gate_results[-1].reason_code in CAPACITY_UNAVAILABLE_REASONS
        for evaluation in evaluations
    )
    health_class_zero_survivors = not survivor_ids and any(
        evaluation.eliminated_at_gate == GATE_CAPACITY_AVAILABILITY
        and evaluation.gate_results[-1].reason_code == HEALTH_EVICTED_REASON_CODE
        for evaluation in evaluations
    )

    if preferred_first:
        selected_profile_id = preferred_first[0]
        reason_codes.append("POLICY_PREFERRED")
        if (
            enable_mission_affinity
            and last_selected_profile_id is not None
            and selected_profile_id == last_selected_profile_id
        ):
            reason_codes.append("MISSION_CONTINUITY")
        reason_codes.append(f"SELECTED:{selected_profile_id}")
        fallback_plan = tuple(
            {
                "profile_id": profile_id,
                "preference_rank": tiered_policy.prefer.index(profile_id),
            }
            for profile_id in preferred_first[1:]
        )
    elif (
        allow_degraded_default
        and routing_environment_class == "development"
        and not hard_gate_denied
        and capacity_class_zero_survivors
        and not health_class_zero_survivors
        and DEGRADED_DEFAULT_PROFILE_ID in PROFILES
    ):
        # Chapter 6.1 gate-5 note: degrade to the declared default rather
        # than escalating when routing has no legal candidate in a
        # development environment class. Hard-gate denials are excluded:
        # they are governance outcomes, not availability failures. A
        # health-driven wipeout is likewise excluded -- degrading into a
        # profile the evidence just evicted would defeat the eviction.
        selected_profile_id = DEGRADED_DEFAULT_PROFILE_ID
        reason_codes.append("DEGRADED_DEFAULT_APPLIED")
        reason_codes.append(f"SELECTED:{selected_profile_id}")
        fallback_plan = ()
    else:
        selected_profile_id = HUMAN_DECISION_TASK
        if hard_gate_denied:
            reason_codes.append("HARD_GATE_APPROVAL_REQUIRED")
        reason_codes.append("NO_ELIGIBLE_WORKER")
        reason_codes.append("ESCALATED_TO_HUMAN_DECISION")
        fallback_plan = ()

    finalized = _finalize_candidates(evaluations, ranked_survivors)

    if (
        model_selection is not None
        and model_selection.enabled
        and selected_profile_id != HUMAN_DECISION_TASK
    ):
        if model_selection.pinned_model_id is not None:
            harness_class = PROFILE_HARNESS_CLASS.get(selected_profile_id)
            if (
                harness_class is not None
                and model_selection.pinned_provider is not None
            ):
                # A pin is an operator instruction, not a match: no strength
                # scoring runs, and the credential tier is the provider's
                # DECLARED tier — no broker binding backs it yet (EDR-0001).
                reason_codes.append(f"PINNED_MODEL:{model_selection.pinned_model_id}")
                reason_codes.append(
                    f"PINNED_PROVIDER:{model_selection.pinned_provider}"
                )
                reason_codes.append(
                    f"PINNED_CREDENTIAL:{MODEL_PROVIDERS[model_selection.pinned_provider]}"
                )
        else:
            openrouter_selection = resolve_openrouter_model(
                profile_id=selected_profile_id,
                workload_class=resolved_workload_class,
            )
            if openrouter_selection is not None:
                reason_codes.append(f"OPENROUTER_MODEL:{openrouter_selection.model_id}")
                reason_codes.append(
                    f"OPENROUTER_CREDENTIAL:{openrouter_selection.credential_provider}"
                )
                for code in openrouter_selection.reason_codes:
                    reason_codes.append(code)

    return RoutingResult(
        workload_class=resolved_workload_class,
        required_capabilities=required_capabilities,
        required_environment_class=environment_class,
        candidates=finalized,
        selected_profile_id=selected_profile_id,
        reason_codes=tuple(reason_codes),
        fallback_plan=fallback_plan,
    )


def _finalize_candidates(
    evaluations: list[CandidateEvaluation],
    ranked_survivors: list[str],
) -> tuple[CandidateEvaluation, ...]:
    """Stamp declared-order preference ranks onto survivors (affinity does
    not rewrite recorded ranks — the audit trail keeps the policy order)."""
    rank_by_profile = {
        profile_id: rank for rank, profile_id in enumerate(ranked_survivors)
    }
    return tuple(
        candidate
        if candidate.profile_id not in rank_by_profile
        else CandidateEvaluation(
            profile_id=candidate.profile_id,
            gate_results=candidate.gate_results,
            eliminated_at_gate=None,
            preference_rank=rank_by_profile[candidate.profile_id],
        )
        for candidate in evaluations
    )
