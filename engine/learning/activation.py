"""Chapter 6.9 learning-activation gates and mode machine -- pure.

`routing.mode` progresses `deterministic → shadow_learning → canary →
promoted_historical`. ROLLBACK is reachable from any state and returns
to the last certified policy, never an untested fallback.

Activation gates are configuration, not product truth. Defaults match
Chapter 6.9. A gate that cannot be computed from a real signal is
reported as unmet (`insufficient_evidence`), never as a pass. No learned
router promotes directly from training metrics.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from engine.contracts.experience_record import ExperienceRecord

RoutingMode = Literal[
    "deterministic",
    "shadow_learning",
    "canary",
    "promoted_historical",
]

PROMOTABLE_MODES: tuple[RoutingMode, ...] = (
    "shadow_learning",
    "canary",
    "promoted_historical",
)

MODE_ORDER: tuple[RoutingMode, ...] = (
    "deterministic",
    "shadow_learning",
    "canary",
    "promoted_historical",
)

PROMOTION_SEQUENCE = (
    "OBSERVE",
    "TRAIN",
    "OFFLINE_EVALUATE",
    "SHADOW",
    "HOLDOUT_EVALUATE",
    "APPROVAL",
    "LIMITED_CANARY",
    "MONITOR",
    "PROMOTE",
)

DEFAULT_ELIGIBLE_PER_CLASS = 300
DEFAULT_ELIGIBLE_GLOBAL = 1_200
DEFAULT_VERIFICATION_COVERAGE = 0.90
DEFAULT_BRIER_CEILING = 0.25
DEFAULT_ECE_CEILING = 0.10
DEFAULT_CANARY_FRACTION = 0.05


@dataclass(frozen=True)
class ActivationThresholds:
    """Chapter 6.9 defaults; raise-able per tenant by governance."""

    eligible_per_class: int = DEFAULT_ELIGIBLE_PER_CLASS
    eligible_global: int = DEFAULT_ELIGIBLE_GLOBAL
    verification_coverage: float = DEFAULT_VERIFICATION_COVERAGE
    brier_ceiling: float = DEFAULT_BRIER_CEILING
    ece_ceiling: float = DEFAULT_ECE_CEILING


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    mandatory: bool
    observed: float | int | None
    required: float | int | None
    reason: str


@dataclass(frozen=True)
class ActivationVerdict:
    """Whether a requested mode advance is permitted."""

    allowed: bool
    requested_mode: RoutingMode
    current_mode: RoutingMode
    gates: tuple[GateResult, ...]
    refused_reasons: tuple[str, ...]


def last_certified_mode(
    *,
    current: RoutingMode,
    certified: RoutingMode | None,
) -> RoutingMode:
    """ROLLBACK returns to the last certified policy, never an untested
    fallback. Uncertified current modes fall back to deterministic."""
    del current
    if certified in MODE_ORDER:
        return certified
    return "deterministic"


def can_transition(*, current: RoutingMode, target: RoutingMode) -> bool:
    """Forward one step, or ROLLBACK-shaped return to a certified earlier
    mode. Skipping (deterministic → canary) is refused."""
    if target == current:
        return True
    try:
        here = MODE_ORDER.index(current)
        there = MODE_ORDER.index(target)
    except ValueError:
        return False
    return there == here + 1


def evaluate_activation_gates(
    *,
    records: list[ExperienceRecord],
    workload_classes: list[str],
    current_mode: RoutingMode,
    requested_mode: RoutingMode,
    thresholds: ActivationThresholds | None = None,
    brier: float | None = None,
    ece: float | None = None,
    holdout_regression: bool | None = None,
    safety_regressions: int = 0,
    fallback_robustness_demonstrated: bool = False,
    drift_within_bounds: bool | None = None,
    propensity_overlap_adequate: bool | None = None,
    claiming_uplift: bool = False,
    frozen_exploitation: bool = True,
    offline_fit_exists: bool = False,
    beats_constant_policy: bool | None = None,
) -> ActivationVerdict:
    """Chapter 6.9: refuse any advance into a learned mode when a
    mandatory gate is unmet. `insufficient_evidence` is a refusal, never
    a silent pass."""
    thresholds = thresholds or ActivationThresholds()
    refused: list[str] = []
    gates: list[GateResult] = []

    if requested_mode not in PROMOTABLE_MODES:
        return ActivationVerdict(
            allowed=False,
            requested_mode=requested_mode,
            current_mode=current_mode,
            gates=(),
            refused_reasons=("requested_mode_not_promotable",),
        )
    if not can_transition(current=current_mode, target=requested_mode):
        return ActivationVerdict(
            allowed=False,
            requested_mode=requested_mode,
            current_mode=current_mode,
            gates=(),
            refused_reasons=("illegal_mode_transition",),
        )

    eligible = [
        row
        for row in records
        if row.experience_origin == "real" and row.eligible_for_routing_training
    ]
    global_count = len(eligible)
    class_counts = Counter(klass for klass in workload_classes[:global_count] if klass)
    min_class = min(class_counts.values()) if class_counts else 0

    gates.append(
        _count_gate(
            "eligible_real_attempts_global",
            observed=global_count,
            required=thresholds.eligible_global,
        )
    )
    gates.append(
        _count_gate(
            "eligible_real_attempts_per_workload_class",
            observed=min_class,
            required=thresholds.eligible_per_class,
        )
    )

    coverage = (
        sum(1 for row in eligible if row.verification_confidence >= 0.9) / global_count
        if global_count
        else 0.0
    )
    gates.append(
        GateResult(
            name="verification_backed_outcome_coverage",
            passed=coverage >= thresholds.verification_coverage,
            mandatory=True,
            observed=coverage,
            required=thresholds.verification_coverage,
            reason=(
                "ok"
                if coverage >= thresholds.verification_coverage
                else "verification_coverage_below_threshold"
            ),
        )
    )

    gates.append(
        _optional_metric_gate(
            "calibration_brier", brier, thresholds.brier_ceiling, below=True
        )
    )
    gates.append(
        _optional_metric_gate(
            "calibration_ece", ece, thresholds.ece_ceiling, below=True
        )
    )
    promotion = requested_mode in ("canary", "promoted_historical")
    gates.append(
        _bool_gate(
            "holdout_no_material_regression",
            holdout_regression is False,
            insufficient=holdout_regression is None,
            mandatory=promotion,
        )
    )
    gates.append(
        GateResult(
            name="safety_regressions_attributable_to_learned_routing",
            passed=safety_regressions == 0,
            mandatory=True,
            observed=safety_regressions,
            required=0,
            reason="ok" if safety_regressions == 0 else "safety_regression_nonzero",
        )
    )
    gates.append(
        _bool_gate(
            "fallback_robustness_under_worker_outage",
            fallback_robustness_demonstrated,
            insufficient=False,
            mandatory=promotion,
        )
    )
    gates.append(
        _bool_gate(
            "distribution_drift_within_bounds",
            drift_within_bounds is True,
            insufficient=drift_within_bounds is None,
            mandatory=promotion,
        )
    )
    if claiming_uplift:
        gates.append(
            _bool_gate(
                "propensity_overlap",
                propensity_overlap_adequate is True,
                insufficient=propensity_overlap_adequate is None,
            )
        )
    gates.append(
        _bool_gate(
            "offline_full_information_fit",
            offline_fit_exists,
            insufficient=False,
        )
    )
    gates.append(
        _bool_gate(
            "frozen_exploitation_first",
            frozen_exploitation,
            insufficient=False,
        )
    )
    gates.append(
        _bool_gate(
            "beats_best_constant_policy",
            beats_constant_policy is True,
            insufficient=beats_constant_policy is None,
            mandatory=promotion,
        )
    )

    for gate in gates:
        if gate.mandatory and not gate.passed:
            refused.append(gate.reason)

    return ActivationVerdict(
        allowed=not refused,
        requested_mode=requested_mode,
        current_mode=current_mode,
        gates=tuple(gates),
        refused_reasons=tuple(refused),
    )


def _count_gate(name: str, *, observed: int, required: int) -> GateResult:
    passed = observed >= required
    return GateResult(
        name=name,
        passed=passed,
        mandatory=True,
        observed=observed,
        required=required,
        reason="ok" if passed else f"{name}_below_threshold",
    )


def _optional_metric_gate(
    name: str,
    observed: float | None,
    ceiling: float,
    *,
    below: bool,
) -> GateResult:
    if observed is None:
        return GateResult(
            name=name,
            passed=False,
            mandatory=True,
            observed=None,
            required=ceiling,
            reason=f"{name}_insufficient_evidence",
        )
    passed = observed <= ceiling if below else observed >= ceiling
    return GateResult(
        name=name,
        passed=passed,
        mandatory=True,
        observed=observed,
        required=ceiling,
        reason="ok" if passed else f"{name}_outside_threshold",
    )


def _bool_gate(
    name: str,
    passed: bool,
    *,
    insufficient: bool,
    mandatory: bool = True,
) -> GateResult:
    if insufficient:
        return GateResult(
            name=name,
            passed=False,
            mandatory=mandatory,
            observed=None,
            required=None,
            reason=f"{name}_insufficient_evidence",
        )
    return GateResult(
        name=name,
        passed=passed,
        mandatory=mandatory,
        observed=1 if passed else 0,
        required=1,
        reason="ok" if passed else f"{name}_unmet",
    )
