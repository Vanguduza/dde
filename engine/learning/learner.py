"""Chapter 6.9 frozen full-information fit -- pure.

A candidate policy's offline phase MUST be a full-information fit over
eligible recorded decisions before any partial-information update path
may exist. This module is that fit: empirical success rates over the
train partition, frozen exploitation mapping, holdout calibration
(Brier/ECE), learner vs best-constant vs incumbent on the identical
window, and distribution drift. It never mutates a bandit, never uses
simulation-origin rows, and never fabricates counterfactual outcomes.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from engine.core.hashing import canonical_json, sha256_hex
from engine.routing.policy import WORKLOAD_CLASSES

FitKind = Literal["frozen_full_information"]

DEFAULT_DRIFT_TV_CEILING = 0.25
ECE_BINS = 10


@dataclass(frozen=True)
class OutcomeObservation:
    """One eligible real decision the learner may fit on."""

    experience_id: UUID
    workload_class: str
    selected_profile_id: str
    success: bool
    holdout_partition: Literal["train", "holdout"]
    down_weighted: bool = False


@dataclass(frozen=True)
class FrozenFit:
    """Result of one offline full-information fit. Not a live router."""

    fit_kind: FitKind
    mapping: dict[str, str]
    constant_policy_profile_id: str
    policy_hash: str
    train_count: int
    holdout_count: int
    brier: float | None
    ece: float | None
    holdout_learner_expected: float | None
    holdout_constant_expected: float | None
    holdout_incumbent_success: float | None
    beats_constant_policy: bool
    holdout_regression: bool | None
    drift_within_bounds: bool | None
    training_experience_ids: tuple[UUID, ...]
    fallback_robustness_demonstrated: bool
    refused_reason: str | None = None


def fit_frozen_policy(
    observations: list[OutcomeObservation],
    *,
    drift_tv_ceiling: float = DEFAULT_DRIFT_TV_CEILING,
    fallback_robustness_demonstrated: bool = False,
) -> FrozenFit:
    """Full-information MLE over observed (class, selected profile, outcome).

    Cold-start (no train partition) is refused -- that is OFFLINE
    EVALUATE rejecting a policy that has not been fitted. Partial-
    information / online updates are structurally out of this function.
    """
    train = [row for row in observations if row.holdout_partition == "train"]
    holdout = [row for row in observations if row.holdout_partition == "holdout"]
    if not train:
        return FrozenFit(
            fit_kind="frozen_full_information",
            mapping={},
            constant_policy_profile_id="",
            policy_hash="",
            train_count=0,
            holdout_count=len(holdout),
            brier=None,
            ece=None,
            holdout_learner_expected=None,
            holdout_constant_expected=None,
            holdout_incumbent_success=None,
            beats_constant_policy=False,
            holdout_regression=None,
            drift_within_bounds=None,
            training_experience_ids=(),
            fallback_robustness_demonstrated=False,
            refused_reason="offline_fit_cold_start",
        )

    class_profile_success: dict[tuple[str, str], list[float]] = defaultdict(list)
    profile_success: dict[str, list[float]] = defaultdict(list)
    for row in train:
        weight = 0.5 if row.down_weighted else 1.0
        outcome = 1.0 if row.success else 0.0
        class_profile_success[(row.workload_class, row.selected_profile_id)].append(
            outcome * weight
        )
        profile_success[row.selected_profile_id].append(outcome * weight)

    mapping: dict[str, str] = {}
    for workload_class in sorted(
        {row.workload_class for row in train} | set(WORKLOAD_CLASSES)
    ):
        candidates = [
            (profile_id, _mean(values))
            for (klass, profile_id), values in class_profile_success.items()
            if klass == workload_class
        ]
        if not candidates:
            continue
        # Prefer higher empirical success, then more observations, then id.
        mapping[workload_class] = max(
            candidates,
            key=lambda item: (
                item[1],
                len(class_profile_success[(workload_class, item[0])]),
                item[0],
            ),
        )[0]

    constant_policy_profile_id = max(
        profile_success,
        key=lambda profile_id: (
            _mean(profile_success[profile_id]),
            len(profile_success[profile_id]),
            profile_id,
        ),
    )

    rates: dict[tuple[str, str], float] = {
        key: _mean(values) for key, values in class_profile_success.items()
    }
    global_rates = {
        profile_id: _mean(values) for profile_id, values in profile_success.items()
    }

    brier: float | None = None
    ece: float | None = None
    learner_expected: float | None = None
    constant_expected: float | None = None
    incumbent_success: float | None = None
    holdout_regression: bool | None = None
    drift: bool | None = None
    beats = False

    if holdout:
        pairs = _holdout_prediction_pairs(holdout, rates)
        if pairs:
            brier = _brier(pairs)
            ece = _ece(pairs)
        learner_scores = [
            _rate_for(
                rates,
                global_rates,
                row.workload_class,
                mapping.get(row.workload_class, constant_policy_profile_id),
            )
            for row in holdout
        ]
        constant_scores = [
            global_rates.get(constant_policy_profile_id, 0.0) for _ in holdout
        ]
        learner_expected = _mean(learner_scores)
        constant_expected = _mean(constant_scores)
        incumbent_success = _mean([1.0 if row.success else 0.0 for row in holdout])
        beats = learner_expected > constant_expected
        holdout_regression = learner_expected < incumbent_success
        drift = (
            _total_variation(
                [row.workload_class for row in train],
                [row.workload_class for row in holdout],
            )
            <= drift_tv_ceiling
        )

    training_ids = tuple(row.experience_id for row in observations)
    policy_hash = sha256_hex(
        canonical_json(
            {
                "fit_kind": "frozen_full_information",
                "mapping": mapping,
                "constant_policy_profile_id": constant_policy_profile_id,
                "training_experience_ids": [str(item) for item in training_ids],
            }
        )
    )
    return FrozenFit(
        fit_kind="frozen_full_information",
        mapping=mapping,
        constant_policy_profile_id=constant_policy_profile_id,
        policy_hash=policy_hash,
        train_count=len(train),
        holdout_count=len(holdout),
        brier=brier,
        ece=ece,
        holdout_learner_expected=learner_expected,
        holdout_constant_expected=constant_expected,
        holdout_incumbent_success=incumbent_success,
        beats_constant_policy=beats,
        holdout_regression=holdout_regression,
        drift_within_bounds=drift,
        training_experience_ids=training_ids,
        fallback_robustness_demonstrated=fallback_robustness_demonstrated,
        refused_reason=None,
    )


def in_canary_slice(task_id: UUID, fraction: float) -> bool:
    """Hash-stable limited-canary assignment. Fraction 0 never assigns;
    1 always does. Does not select a profile -- only whether this task
    is in the learned slice."""
    if fraction <= 0:
        return False
    if fraction >= 1:
        return True
    bucket = int(sha256_hex(str(task_id))[:8], 16) % 10_000
    return bucket < int(fraction * 10_000)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _rate_for(
    rates: dict[tuple[str, str], float],
    global_rates: dict[str, float],
    workload_class: str,
    profile_id: str,
) -> float:
    if (workload_class, profile_id) in rates:
        return rates[(workload_class, profile_id)]
    return global_rates.get(profile_id, 0.0)


def _holdout_prediction_pairs(
    holdout: list[OutcomeObservation],
    rates: dict[tuple[str, str], float],
) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for row in holdout:
        predicted = rates.get((row.workload_class, row.selected_profile_id))
        if predicted is None:
            continue
        pairs.append((predicted, 1.0 if row.success else 0.0))
    return pairs


def _brier(pairs: list[tuple[float, float]]) -> float:
    return sum((predicted - observed) ** 2 for predicted, observed in pairs) / len(
        pairs
    )


def _ece(pairs: list[tuple[float, float]], bins: int = ECE_BINS) -> float:
    if not pairs:
        return 0.0
    total = len(pairs)
    error = 0.0
    for index in range(bins):
        lo = index / bins
        hi = (index + 1) / bins
        bucket = [
            pair
            for pair in pairs
            if (pair[0] >= lo and pair[0] < hi)
            or (index == bins - 1 and pair[0] == 1.0)
        ]
        if not bucket:
            continue
        confidence = _mean([pair[0] for pair in bucket])
        accuracy = _mean([pair[1] for pair in bucket])
        error += (len(bucket) / total) * abs(accuracy - confidence)
    return error


def _total_variation(train_classes: list[str], holdout_classes: list[str]) -> float:
    train_counts = Counter(train_classes)
    holdout_counts = Counter(holdout_classes)
    keys = set(train_counts) | set(holdout_counts)
    train_n = len(train_classes) or 1
    holdout_n = len(holdout_classes) or 1
    return 0.5 * sum(
        abs(train_counts[key] / train_n - holdout_counts[key] / holdout_n)
        for key in keys
    )
