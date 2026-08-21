"""Chapter 6.1's routing pipeline, implemented exactly to its stated
precedence: gates 0-5 are hard gates ("a candidate that fails any of gates
0-5 is removed, not penalised. No economic score can compensate...");
gates 6-9 (§6.6-6.9: performance estimate, economic score, route critic,
escalation) "only ever reorder legal candidates". Stage 1 has no real
performance/cost telemetry (Chapter 6.5's telemetry pipeline is DDE-035,
S4) and no Route Critic (triggered-only, §6.6, deferred with it) — the one
real, declared-policy signal available for ranking survivors is Chapter
6.2's own `prefer[]` ordering, so that is gates 6-7's entire Stage 1
implementation: it is the deterministic tie-break, not a placeholder for
one.

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

`visual_analysis` is intentionally unreachable from `classify_workload` in
Stage 1 (see `engine.routing.policy`'s module docstring) but is still a
real workload class any caller may pass to `evaluate` directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from engine.contracts.task import Task
from engine.routing.policy import (
    HUMAN_DECISION_TASK,
    RISK_ORDER,
    WORKLOAD_CLASSES,
)
from engine.routing.registry import PROFILES, required_environment_class

GATE_HARD_POLICY = 0
GATE_CAPABILITY_REQUIREMENTS = 1
GATE_WORKER_ELIGIBILITY = 3
GATE_ENVIRONMENT_COMPATIBILITY = 4
GATE_CAPACITY_AVAILABILITY = 5


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

    # Gate 5: no worker health/quota/concurrency/budget signal exists yet
    # (Chapter 8 Worker Manager, DDE-011) — a real pass-through, not a
    # fabricated health check, until that data exists.
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
) -> RoutingResult:
    """Run every registered profile through Chapter 6.1's gates 0-5 for
    `task`, then rank survivors by Chapter 6.2's declared `prefer[]` order
    (gates 6-7's Stage 1 tie-break) and select the top-ranked one. Returns
    a real `HUMAN_DECISION_TASK` escalation, never an exception, when zero
    candidates survive — Chapter 6.1 gate 9 treats escalation as a normal,
    recordable routing outcome, not a failure."""
    resolved_workload_class = workload_class or classify_workload(task)
    policy = WORKLOAD_CLASSES[resolved_workload_class]
    required_capabilities = policy.require
    environment_class = required_environment_class(required_capabilities)
    hard_gate_denied = task.requires_approval

    evaluations: list[CandidateEvaluation] = []
    survivor_ids: list[str] = []
    allow_stale = routing_environment_class == "development"
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
            prefer=policy.prefer,
            forbid_generator=policy.forbid_generator,
            min_risk=policy.min_risk,
            max_risk=policy.max_risk,
            previous_generator_profile_id=previous_generator_profile_id,
            certification_status=status,
            allow_stale=allow_stale,
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

    ranked_survivors = sorted(survivor_ids, key=policy.prefer.index)
    rank_by_profile = {
        profile_id: rank for rank, profile_id in enumerate(ranked_survivors)
    }
    finalized = tuple(
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

    reason_codes = [f"WORKLOAD_CLASSIFIED:{resolved_workload_class}"]
    if ranked_survivors:
        selected_profile_id = ranked_survivors[0]
        reason_codes.append("POLICY_PREFERRED")
        reason_codes.append(f"SELECTED:{selected_profile_id}")
        fallback_plan = tuple(
            {"profile_id": profile_id, "preference_rank": rank_by_profile[profile_id]}
            for profile_id in ranked_survivors[1:]
        )
    else:
        selected_profile_id = HUMAN_DECISION_TASK
        if hard_gate_denied:
            reason_codes.append("HARD_GATE_APPROVAL_REQUIRED")
        reason_codes.append("NO_ELIGIBLE_WORKER")
        reason_codes.append("ESCALATED_TO_HUMAN_DECISION")
        fallback_plan = ()

    return RoutingResult(
        workload_class=resolved_workload_class,
        required_capabilities=required_capabilities,
        required_environment_class=environment_class,
        candidates=finalized,
        selected_profile_id=selected_profile_id,
        reason_codes=tuple(reason_codes),
        fallback_plan=fallback_plan,
    )
