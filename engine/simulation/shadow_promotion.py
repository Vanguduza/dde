"""Shadow-mode policy promotion (comparable-systems adoption #8) over
recorded Chapter 6.5 routing telemetry.

**Shadow evaluation only.** Nothing in this module writes to, selects, or
reorders live routing policy: `engine.routing.policy` / `engine.routing.
rules` are read *never* here and mutated *never anywhere* -- the live
selection path is `RoutingService.decide`, which this module does not
touch. A candidate policy table is scored offline against real
`routing_decision_outcomes` rows, and the only durable effect is a
`routing_simulation_runs` row (`run_kind="shadow_promotion"`) recording
the measured quadrant counts, deltas and the promotion verdict. Promoting
a candidate into live selection remains a human, Chapter 6.5-governed act
outside this module's scope.

**Decision versus ground truth.** A routing policy controls exactly one
thing: whether a task is *routed* -- here, whether the recorded
`verification_confidence` clears the policy's `accept_confidence_floor`.
Whether the task actually passed is ground truth carried on the row
(`actual_verified_outcome`) and no policy opinion can change it. Every
replayed decision therefore lands in exactly one of four quadrants:

* routed AND actually passed      -> a success;
* routed AND actually failed      -> a wasted accept (real effort burned);
* rejected AND would have passed  -> a missed pass;
* rejected AND actually failed    -> a correct rejection.

**Why raw accept-rate is no longer the promotion key.** An earlier
revision promoted the candidate whose accept-rate strictly beat the
baseline's, with "accepted" defined as *passed AND confident enough*.
That conflated the router's decision with the outcome: accepting doomed
work was invisible to the metric, so any floor below the baseline's
mechanically won promotion even when every newly accepted task then
failed -- the gate rewarded lowering standards. Promotion now keys on
`success_yield` (routed-and-passed over ALL decisions), which only rises
when newly routed tasks genuinely pass or fewer routed tasks fail;
permissiveness alone can no longer win.

**Honest cost disclosure.** `RoutingDecisionOutcome` carries
`disclosed_gaps` naming `actual_token_cost`/`actual_tool_cost` as not
recorded (`engine.telemetry.model.ACTUAL_COST_GAP_DISCLOSED`). The cost
deltas below are therefore computed from `elapsed_seconds` -- the one
real cost-shaped signal on every row -- and every persisted result
carries the same disclosure in `cost_basis` rather than a fabricated
dollar figure. Mean cost is measured over the *routed* set including
failed routed tasks: their elapsed time is spent just as surely.

**Rollback trigger.** Promotion requires a *pre-registered* rollback
trigger from the caller: a predicate over the candidate's measured
metrics (success yield, wasted accepts, cost, gate failures) that, if it
fires on the promoted policy, defines the reversion condition in advance
-- not a post-hoc rationalisation after promotion. Verdict, quadrant
counts and deltas are persisted on the run row so the contract is
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


@dataclass(frozen=True)
class PolicyOutcome:
    """One decision replayed under a policy table.

    `routed` is the policy's decision (confidence clears its floor);
    `actual_passed` is ground truth read off the recorded row. Keeping
    the two apart is what makes a wasted accept measurable at all: a
    policy can route a task that then fails, and the metrics must see
    both halves of that fact.
    """

    routed: bool
    actual_passed: bool
    gate_failed: bool
    cost: float | None


@dataclass(frozen=True)
class PolicyMetrics:
    """Measured aggregates over one policy's replays.

    The four counts partition `decisions` exactly. `success_yield` is
    the primary metric: the fraction of ALL decisions that ended
    routed-and-passed, so rejecting a passable task costs the miss just
    as routing a doomed task costs the waste. `gate_fail_rate`,
    `wasted_accept_rate` and mean cost are over the *routed* set only --
    a rejection never spends a gate or a second of elapsed time, so
    counting rejected decisions there would dilute every policy toward
    identical mediocrity.
    """

    decisions: int
    successes: int
    wasted_accepts: int
    missed_passes: int
    correct_rejections: int
    routed_rate: float
    success_yield: float
    wasted_accept_rate: float
    gate_fail_rate: float
    mean_cost: float | None
    cost_samples: int


@dataclass(frozen=True)
class ShadowPromotionRequest:
    """A candidate policy evaluation over recorded outcomes.

    `candidate_policy` and `baseline_policy` are dict-shaped
    configuration (the same shape `engine.routing.policy` tables use) --
    no schema migration: everything persists inside the simulation run's
    existing JSONB `result` payload. `rollback_trigger` is the
    pre-registered reversion predicate; it is called with the candidate's
    measured metrics and returns True when the promoted policy must be
    rolled back. `wasted_accept_tolerance` permits the candidate's
    wasted-accept rate to exceed the baseline's by at most that absolute
    amount without automatic refusal (default 0.0: no regression).
    """

    candidate_policy: dict[str, Any]
    max_cost_regression: float
    rollback_trigger: Callable[[PolicyMetrics], bool]
    baseline_policy: dict[str, Any] = field(default_factory=dict)
    wasted_accept_tolerance: float = 0.0


@dataclass(frozen=True)
class ShadowPromotionDecision:
    """The measured verdict over one candidate."""

    promoted: bool
    baseline: PolicyMetrics
    candidate: PolicyMetrics
    success_yield_delta: float
    routed_rate_delta: float
    wasted_accept_delta: float
    cost_delta: float | None
    gate_fail_delta: float
    cost_basis: str
    reasons: list[str]
    rollback_trigger_fired: bool


def replay(
    policy: dict[str, Any],
    outcomes: list[RoutingDecisionOutcome],
) -> list[PolicyOutcome]:
    """Replay every recorded outcome under `policy`, decision and truth
    kept apart.

    The policy's sole lever here is its `accept_confidence_floor`
    (default 0.0): a decision is *routed* when the row's real
    verification confidence meets the floor. Ground truth is read
    straight off the row -- `actual_verified_outcome == "PASSED"` --
    and is deliberately NOT folded into the routing decision. An earlier
    revision accepted only rows that both cleared the floor and passed;
    folding decision into truth made accepting doomed work
    unrepresentable, hence unmeasurable, hence free. The four-quadrant
    accounting in `measure()` needs both signals independently.

    A decision is *gate-failed* when the real outcome failed with a real
    recovery action naming a gate (approval/human intervention);
    everything is read off the recorded row, nothing is re-derived or
    fabricated.
    """
    floor = float(policy.get("accept_confidence_floor", 0.0))
    replayed: list[PolicyOutcome] = []
    for outcome in outcomes:
        replayed.append(
            PolicyOutcome(
                routed=outcome.verification_confidence >= floor,
                actual_passed=outcome.actual_verified_outcome == "PASSED",
                gate_failed=bool(
                    outcome.human_intervention_required or outcome.escalated
                ),
                cost=outcome.elapsed_seconds,
            )
        )
    return replayed


def measure(replayed: list[PolicyOutcome]) -> PolicyMetrics:
    """Aggregate replays into quadrant counts and the measured rates.

    Denominators are chosen so no policy scores well by refusing to look
    at hard work: `success_yield` spans every decision (routing away a
    passable task costs the miss), while the routed population owns the
    gate-fail, wasted-accept and cost measurements. Failed routed tasks
    stay in the cost mean: their elapsed time is spent just as surely as
    a success's.
    """
    decisions = len(replayed)
    if decisions == 0:
        return PolicyMetrics(
            decisions=0,
            successes=0,
            wasted_accepts=0,
            missed_passes=0,
            correct_rejections=0,
            routed_rate=0.0,
            success_yield=0.0,
            wasted_accept_rate=0.0,
            gate_fail_rate=0.0,
            mean_cost=None,
            cost_samples=0,
        )
    successes = sum(1 for item in replayed if item.routed and item.actual_passed)
    wasted_accepts = sum(
        1 for item in replayed if item.routed and not item.actual_passed
    )
    missed_passes = sum(
        1 for item in replayed if not item.routed and item.actual_passed
    )
    correct_rejections = sum(
        1 for item in replayed if not item.routed and not item.actual_passed
    )
    routed = [item for item in replayed if item.routed]
    gate_failed = sum(1 for item in routed if item.gate_failed)
    costs = [item.cost for item in routed if item.cost is not None]
    return PolicyMetrics(
        decisions=decisions,
        successes=successes,
        wasted_accepts=wasted_accepts,
        missed_passes=missed_passes,
        correct_rejections=correct_rejections,
        routed_rate=len(routed) / decisions,
        success_yield=successes / decisions,
        wasted_accept_rate=(wasted_accepts / len(routed)) if routed else 0.0,
        gate_fail_rate=(gate_failed / len(routed)) if routed else 0.0,
        mean_cost=(sum(costs) / len(costs)) if costs else None,
        cost_samples=len(costs),
    )


def evaluate_shadow_promotion(
    request: ShadowPromotionRequest,
    outcomes: list[RoutingDecisionOutcome],
) -> ShadowPromotionDecision:
    """Score the candidate over recorded outcomes and return the verdict.

    Promotion requires ALL of:
    1. candidate `success_yield` STRICTLY beats the baseline's -- the
       share of all decisions ending routed-and-passed. Raw accept-rate
       is no longer the promotion key: under it any floor below the
       baseline's mechanically improved the metric even when every newly
       accepted task failed, so the gate rewarded pure permissiveness
       instead of genuine throughput;
    2. the candidate's `wasted_accept_rate` does not regress beyond
       `request.wasted_accept_tolerance`;
    3. candidate cost does not regress beyond `max_cost_regression`
       (a ratio of baseline mean cost; when either side lacks a cost
       signal the cost gate is *not* silently waived -- the delta is
       `None`, `cost_basis` discloses why, and promotion is refused);
    4. the caller's pre-registered rollback trigger does not fire on the
       candidate's measured metrics.
    """
    baseline = measure(replay(request.baseline_policy, outcomes))
    candidate = measure(replay(request.candidate_policy, outcomes))
    reasons: list[str] = []

    success_yield_delta = candidate.success_yield - baseline.success_yield
    routed_rate_delta = candidate.routed_rate - baseline.routed_rate
    wasted_accept_delta = candidate.wasted_accept_rate - baseline.wasted_accept_rate
    gate_fail_delta = candidate.gate_fail_rate - baseline.gate_fail_rate

    if baseline.decisions == 0 or candidate.decisions == 0:
        reasons.append("no recorded outcomes to evaluate over")
        return ShadowPromotionDecision(
            promoted=False,
            baseline=baseline,
            candidate=candidate,
            success_yield_delta=success_yield_delta,
            routed_rate_delta=routed_rate_delta,
            wasted_accept_delta=wasted_accept_delta,
            cost_delta=None,
            gate_fail_delta=gate_fail_delta,
            cost_basis="no outcomes",
            reasons=reasons,
            rollback_trigger_fired=False,
        )

    if success_yield_delta <= 0:
        reasons.append(
            f"success_yield did not improve: {candidate.success_yield:.4f} vs "
            f"baseline {baseline.success_yield:.4f}"
        )

    wasted_ceiling = baseline.wasted_accept_rate + request.wasted_accept_tolerance
    if candidate.wasted_accept_rate > wasted_ceiling:
        reasons.append(
            f"wasted_accept_rate {candidate.wasted_accept_rate:.4f} exceeds "
            f"tolerance ceiling {wasted_ceiling:.4f} (baseline "
            f"{baseline.wasted_accept_rate:.4f} + "
            f"{request.wasted_accept_tolerance:.4f})"
        )

    cost_basis = (
        "mean elapsed_seconds over routed decisions (disclosed gap: "
        "actual_token_cost/actual_tool_cost not recorded on "
        f"routing_decision_outcomes rows -- {ACTUAL_COST_GAP_DISCLOSED})"
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
        and success_yield_delta > 0
        and cost_delta is not None
        and not rollback_fired
    )
    if promoted:
        reasons.append(
            f"success_yield +{success_yield_delta:.4f}, wasted accepts within "
            "tolerance, cost within threshold, rollback trigger quiet"
        )
    return ShadowPromotionDecision(
        promoted=promoted,
        baseline=baseline,
        candidate=candidate,
        success_yield_delta=success_yield_delta,
        routed_rate_delta=routed_rate_delta,
        wasted_accept_delta=wasted_accept_delta,
        cost_delta=cost_delta,
        gate_fail_delta=gate_fail_delta,
        cost_basis=cost_basis,
        reasons=reasons,
        rollback_trigger_fired=rollback_fired,
    )
