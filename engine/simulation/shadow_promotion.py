"""Shadow-mode policy promotion (comparable-systems adoption #8) over
recorded Chapter 6.5 routing telemetry.

**Shadow evaluation only.** Nothing in this module writes to, selects, or
reorders live routing policy: `engine.routing.policy` / `engine.routing.
rules` are read *never* here and mutated *never anywhere* -- the live
selection path is `RoutingService.decide`, which this module does not
touch. A candidate policy table is scored offline against real
`routing_decision_outcomes` rows, and the only durable effect is a
`routing_simulation_runs` row (`run_kind="shadow_promotion"`) recording
the measured deltas and the promotion verdict. Promoting a candidate into
live selection remains a human, Chapter 6.5-governed act outside this
module's scope.

**Honest cost disclosure.** `RoutingDecisionOutcome` carries
`disclosed_gaps` naming `actual_token_cost`/`actual_tool_cost` as not
recorded (`engine.telemetry.model.ACTUAL_COST_GAP_DISCLOSED`). The cost
deltas below are therefore computed from `elapsed_seconds` -- the one
real cost-shaped signal on every row -- and every persisted result
carries the same disclosure in `cost_basis` rather than a fabricated
dollar figure.

**Rollback trigger.** Promotion requires a *pre-registered* rollback
trigger from the caller: a predicate over (accept_rate, cost, gate_fail)
that, if it ever fires on the promoted policy, defines the reversion
condition in advance -- not a post-hoc rationalisation after promotion.
The trigger is persisted on the run row so the reversion contract is
auditable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from engine.contracts.routing_decision_outcome import RoutingDecisionOutcome
from engine.telemetry.model import ACTUAL_COST_GAP_DISCLOSED

#: The `run_kind` discriminator value this module persists.
SHADOW_PROMOTION_RUN_KIND = "shadow_promotion"

#: Cost-regression tolerance semantics: `max_cost_regression` is a
#: caller-supplied *ratio* of baseline mean elapsed seconds (0.10 == the
#: candidate may be at most 10% slower on mean elapsed time).
DEFAULT_ROLLBACK_EXHAUSTION_RATE = 0.5


@dataclass(frozen=True)
class PolicyOutcome:
    """One decision replayed under a policy table."""

    accepted: bool
    gate_failed: bool
    cost: float | None


@dataclass(frozen=True)
class PolicyMetrics:
    """Measured aggregates over one policy's replays."""

    decisions: int
    accept_rate: float
    gate_fail_rate: float
    mean_cost: float | None
    cost_samples: int


@dataclass(frozen=True)
class ShadowPromotionRequest:
    """A candidate policy evaluation over recorded outcomes.

    `candidate_policy` is dict-shaped configuration (the same shape
    `engine.routing.policy` tables use) -- no schema migration: it
    persists inside the simulation run's existing JSONB `result` payload.
    `rollback_trigger` is the pre-registered reversion predicate; it is
    called with the candidate's measured metrics and returns True when the
    promoted policy must be rolled back.
    """

    candidate_policy: dict[str, Any]
    max_cost_regression: float
    rollback_trigger: Callable[[PolicyMetrics], bool]
    baseline_policy: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ShadowPromotionDecision:
    """The measured verdict over one candidate."""

    promoted: bool
    baseline: PolicyMetrics
    candidate: PolicyMetrics
    accept_rate_delta: float
    cost_delta: float | None
    gate_fail_delta: float
    cost_basis: str
    reasons: list[str]
    rollback_trigger_fired: bool


def replay(
    policy: dict[str, Any],
    outcomes: list[RoutingDecisionOutcome],
) -> list[PolicyOutcome]:
    """Replay every recorded outcome under `policy`.

    The candidate table may carry a `accept_confidence_floor` entry
    (default 0.0): a replayed decision is *accepted* when its real
    verification passed and its real verification confidence meets the
    candidate's floor, and *gate-failed* when the real outcome failed with
    a real recovery action naming a gate (approval/human intervention).
    Everything is read off the recorded row; nothing is re-derived or
    fabricated.
    """
    floor = float(policy.get("accept_confidence_floor", 0.0))
    replayed: list[PolicyOutcome] = []
    for outcome in outcomes:
        passed = outcome.actual_verified_outcome == "PASSED"
        accepted = passed and outcome.verification_confidence >= floor
        gate_failed = bool(outcome.human_intervention_required or outcome.escalated)
        cost = outcome.elapsed_seconds
        replayed.append(
            PolicyOutcome(accepted=accepted, gate_failed=gate_failed, cost=cost)
        )
    return replayed


def measure(replayed: list[PolicyOutcome]) -> PolicyMetrics:
    """Aggregate replays into the three measured deltas' ingredients.

    Rates and costs are measured over what a routing decision is for --
    accepted decisions: `accept_rate` is over all replayed rows, while
    `gate_fail_rate` and mean cost are over the *accepted* set only. A
    gate failure among rejected decisions is not a property of the
    accepted population; measuring there would make every policy's cost
    identical by construction and the delta meaningless.
    """
    decisions = len(replayed)
    if decisions == 0:
        return PolicyMetrics(
            decisions=0,
            accept_rate=0.0,
            gate_fail_rate=0.0,
            mean_cost=None,
            cost_samples=0,
        )
    accepted = [item for item in replayed if item.accepted]
    gate_failed = sum(1 for item in accepted if item.gate_failed)
    costs = [item.cost for item in accepted if item.cost is not None]
    return PolicyMetrics(
        decisions=decisions,
        accept_rate=len(accepted) / decisions,
        gate_fail_rate=(gate_failed / len(accepted)) if accepted else 0.0,
        mean_cost=(sum(costs) / len(costs)) if costs else None,
        cost_samples=len(costs),
    )


def evaluate_shadow_promotion(
    request: ShadowPromotionRequest,
    outcomes: list[RoutingDecisionOutcome],
) -> ShadowPromotionDecision:
    """Score the candidate over recorded outcomes and return the verdict.

    Promotion requires ALL of:
    1. candidate accept-rate strictly beats baseline;
    2. candidate cost does not regress beyond `max_cost_regression`
       (a ratio of baseline mean cost; when either side lacks a cost
       signal the cost gate is *not* silently waived -- the delta is
       `None`, `cost_basis` discloses why, and promotion is refused);
    3. the caller's pre-registered rollback trigger does not fire on the
       candidate's measured metrics.
    """
    baseline = measure(replay(request.baseline_policy, outcomes))
    candidate = measure(replay(request.candidate_policy, outcomes))
    reasons: list[str] = []

    accept_rate_delta = candidate.accept_rate - baseline.accept_rate
    gate_fail_delta = candidate.gate_fail_rate - baseline.gate_fail_rate

    if baseline.decisions == 0 or candidate.decisions == 0:
        reasons.append("no recorded outcomes to evaluate over")
        return ShadowPromotionDecision(
            promoted=False,
            baseline=baseline,
            candidate=candidate,
            accept_rate_delta=accept_rate_delta,
            cost_delta=None,
            gate_fail_delta=gate_fail_delta,
            cost_basis="no outcomes",
            reasons=reasons,
            rollback_trigger_fired=False,
        )

    if accept_rate_delta <= 0:
        reasons.append(
            f"accept_rate did not improve: {candidate.accept_rate:.4f} vs "
            f"baseline {baseline.accept_rate:.4f}"
        )

    cost_basis = (
        "mean elapsed_seconds (disclosed gap: actual_token_cost/"
        "actual_tool_cost not recorded on routing_decision_outcomes rows -- "
        f"{ACTUAL_COST_GAP_DISCLOSED})"
    )
    cost_delta: float | None
    if baseline.mean_cost is None or candidate.mean_cost is None:
        cost_delta = None
        reasons.append(
            "cost signal absent on one side; refusing to waive the cost gate "
            "on missing data"
        )
    else:
        cost_delta = candidate.mean_cost - baseline.mean_cost
        ceiling = baseline.mean_cost * (1.0 + request.max_cost_regression)
        if candidate.mean_cost > ceiling:
            reasons.append(
                f"mean cost {candidate.mean_cost:.2f}s exceeds regression "
                f"ceiling {ceiling:.2f}s (baseline {baseline.mean_cost:.2f}s "
                f"+ {request.max_cost_regression:.0%})"
            )

    rollback_fired = request.rollback_trigger(candidate)
    if rollback_fired:
        reasons.append("pre-registered rollback trigger fired on candidate metrics")

    promoted = (
        not reasons
        and accept_rate_delta > 0
        and cost_delta is not None
        and not rollback_fired
    )
    if promoted:
        reasons.append(
            f"accept_rate +{accept_rate_delta:.4f}, cost within threshold, "
            "rollback trigger quiet"
        )
    return ShadowPromotionDecision(
        promoted=promoted,
        baseline=baseline,
        candidate=candidate,
        accept_rate_delta=accept_rate_delta,
        cost_delta=cost_delta,
        gate_fail_delta=gate_fail_delta,
        cost_basis=cost_basis,
        reasons=reasons,
        rollback_trigger_fired=rollback_fired,
    )
