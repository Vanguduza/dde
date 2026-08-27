"""Chapter 18.6 removal-test rule.

A candidate may be proposed for removal only when a measurement shows
verified outcomes would not drop and cost per verified success would not
increase. Missing measurement fail-closes to KEEP. This function never
deletes a subsystem — PROPOSE_EDR is the only non-keep verdict.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.overhead.formula import cost_per_verified_success

KEEP = "KEEP"
PROPOSE_EDR = "PROPOSE_EDR"


@dataclass(frozen=True)
class RemovalMeasurement:
    """Counterfactual vs current. None on any field means unmeasured."""

    verified_success_now: int | None
    overhead_tokens_now: int | None
    verified_success_if_removed: int | None
    overhead_tokens_if_removed: int | None


@dataclass(frozen=True)
class RemovalVerdict:
    candidate: str
    decision: str
    reason: str
    cost_now: float | None
    cost_if_removed: float | None


def evaluate_candidate(
    *,
    candidate: str,
    measurement: RemovalMeasurement,
) -> RemovalVerdict:
    """Production rule for §18.6. Call site: `ReadinessReview.run`."""
    cost_now = _cost(measurement.overhead_tokens_now, measurement.verified_success_now)
    cost_if_removed = _cost(
        measurement.overhead_tokens_if_removed,
        measurement.verified_success_if_removed,
    )
    if (
        measurement.verified_success_now is None
        or measurement.verified_success_if_removed is None
        or cost_now is None
        or cost_if_removed is None
    ):
        return RemovalVerdict(
            candidate=candidate,
            decision=KEEP,
            reason="unmeasured",
            cost_now=cost_now,
            cost_if_removed=cost_if_removed,
        )
    if measurement.verified_success_if_removed < measurement.verified_success_now:
        return RemovalVerdict(
            candidate=candidate,
            decision=KEEP,
            reason="verified_outcomes_would_drop",
            cost_now=cost_now,
            cost_if_removed=cost_if_removed,
        )
    if cost_if_removed > cost_now:
        return RemovalVerdict(
            candidate=candidate,
            decision=KEEP,
            reason="cost_per_verified_success_would_increase",
            cost_now=cost_now,
            cost_if_removed=cost_if_removed,
        )
    return RemovalVerdict(
        candidate=candidate,
        decision=PROPOSE_EDR,
        reason="measurement_justifies_edr",
        cost_now=cost_now,
        cost_if_removed=cost_if_removed,
    )


def _cost(overhead: int | None, successes: int | None) -> float | None:
    if overhead is None or successes is None:
        return None
    return cost_per_verified_success(overhead, successes)
