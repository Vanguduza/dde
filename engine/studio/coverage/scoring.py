"""DDE-069 coverage scoring -- pure, so the honesty rules are testable.

The rule this module exists to enforce: *unknown is not failed, and
neither is a number*. Four outcomes are kept apart end to end --

`SATISFIED`     the obligation's node exists and any verification it
                requires has actually passed;
`MISSING`       no node implements it. This is a failure;
`UNVERIFIED`    a node exists but a required check has not run. This is
                unknown, and it is what forbids a confident percentage;
`BLOCKED`       recorded as blocked by an explicit decision;
`WAIVED`        deferred or not-applicable by an explicit decision, and
                therefore outside the denominator entirely.

A dimension is `ASSESSED` only when nothing in it is unknown. The
weighted summary is a number only when every dimension is ASSESSED;
otherwise it is `None` and the golden coverage ring renders an em-dash.
That is the whole point: one percentage must never launder a project
nobody has actually checked.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from engine.contracts.frontend_contract import Obligation
from engine.contracts.frontend_coverage_snapshot import DimensionResult, Finding


class ObligationOutcome(StrEnum):
    SATISFIED = "SATISFIED"
    MISSING = "MISSING"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"
    WAIVED = "WAIVED"


class CoverageState(StrEnum):
    UNASSESSED = "UNASSESSED"
    PARTIAL = "PARTIAL"
    ASSESSED = "ASSESSED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ObligationEvaluation:
    obligation: Obligation
    outcome: ObligationOutcome
    detail: str


def evaluate_obligation(
    obligation: Obligation,
    *,
    implemented_keys: frozenset[str],
    passing_verifications: Mapping[str, frozenset[str]],
) -> ObligationEvaluation:
    """Decide one obligation's outcome.

    `passing_verifications` maps a pxg_key to the evidence kinds that
    have actually passed for it. A required kind that is absent yields
    UNVERIFIED -- deliberately not SATISFIED, and deliberately not
    MISSING, because "built but unchecked" is its own state.
    """
    if obligation.applicability == "BLOCKED_RECORDED":
        return ObligationEvaluation(
            obligation,
            ObligationOutcome.BLOCKED,
            f"blocked by {obligation.applicability_decision_ref}",
        )
    if obligation.applicability in ("DEFERRED_APPROVED", "NOT_APPLICABLE_APPROVED"):
        return ObligationEvaluation(
            obligation,
            ObligationOutcome.WAIVED,
            f"{obligation.applicability} per {obligation.applicability_decision_ref}",
        )
    if obligation.pxg_key not in implemented_keys:
        return ObligationEvaluation(
            obligation,
            ObligationOutcome.MISSING,
            f"no PXG node implements {obligation.pxg_key}",
        )
    required_kinds = frozenset(obligation.verification_kinds)
    if not required_kinds:
        return ObligationEvaluation(
            obligation, ObligationOutcome.SATISFIED, "implemented; no check required"
        )
    passed = passing_verifications.get(obligation.pxg_key, frozenset())
    outstanding = sorted(required_kinds - passed)
    if outstanding:
        return ObligationEvaluation(
            obligation,
            ObligationOutcome.UNVERIFIED,
            "implemented but these required checks have not passed: "
            + ", ".join(outstanding),
        )
    return ObligationEvaluation(
        obligation, ObligationOutcome.SATISFIED, "implemented and verified"
    )


def summarise_dimension(
    dimension: str, evaluations: Sequence[ObligationEvaluation]
) -> DimensionResult:
    counts = {outcome: 0 for outcome in ObligationOutcome}
    for evaluation in evaluations:
        counts[evaluation.outcome] += 1

    # The denominator excludes waivers: an approved not-applicable
    # obligation is not a gap, and counting it as one would push teams to
    # stop recording waivers at all.
    required = (
        counts[ObligationOutcome.SATISFIED]
        + counts[ObligationOutcome.MISSING]
        + counts[ObligationOutcome.UNVERIFIED]
        + counts[ObligationOutcome.BLOCKED]
    )
    unknown = counts[ObligationOutcome.UNVERIFIED]
    blocked = counts[ObligationOutcome.BLOCKED]

    if required == 0:
        state = CoverageState.UNASSESSED
    elif blocked and blocked == required:
        state = CoverageState.BLOCKED
    elif unknown or blocked:
        state = CoverageState.PARTIAL
    else:
        state = CoverageState.ASSESSED

    percent = (
        round(100.0 * counts[ObligationOutcome.SATISFIED] / required, 2)
        if state is CoverageState.ASSESSED
        else None
    )
    return DimensionResult(
        dimension=dimension,
        state=state.value,
        required_count=required,
        satisfied_count=counts[ObligationOutcome.SATISFIED],
        missing_count=counts[ObligationOutcome.MISSING],
        unverified_count=unknown,
        blocked_count=blocked,
        waived_count=counts[ObligationOutcome.WAIVED],
        percent=percent,
    )


def summarise(
    dimensions: Sequence[DimensionResult],
) -> tuple[CoverageState, float | None]:
    """Roll dimensions up without inventing certainty.

    A weighted percentage exists only when every dimension is ASSESSED.
    Weighting is by required_count, so a dimension with one obligation
    cannot outvote a dimension with forty.
    """
    assessable = [item for item in dimensions if item.required_count > 0]
    if not assessable:
        return CoverageState.UNASSESSED, None
    states = {CoverageState(item.state) for item in assessable}
    if states == {CoverageState.BLOCKED}:
        return CoverageState.BLOCKED, None
    if states != {CoverageState.ASSESSED}:
        return CoverageState.PARTIAL, None
    satisfied = sum(item.satisfied_count for item in assessable)
    required = sum(item.required_count for item in assessable)
    return CoverageState.ASSESSED, round(100.0 * satisfied / required, 2)


def findings_for(
    evaluations: Iterable[ObligationEvaluation],
) -> tuple[Finding, ...]:
    """Every non-satisfied outcome becomes a drill-down finding."""
    kinds = {
        ObligationOutcome.MISSING: "MISSING",
        ObligationOutcome.UNVERIFIED: "UNVERIFIED",
        ObligationOutcome.BLOCKED: "BLOCKED",
        ObligationOutcome.WAIVED: "WAIVED",
    }
    return tuple(
        Finding(
            finding_kind=kinds[item.outcome],
            dimension=item.obligation.dimension,
            pxg_key=item.obligation.pxg_key,
            obligation_id=item.obligation.obligation_id,
            detail=item.detail,
        )
        for item in evaluations
        if item.outcome is not ObligationOutcome.SATISFIED
    )
