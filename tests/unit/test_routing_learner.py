"""Chapter 6.9 frozen full-information fit -- pure algorithm tests."""

from __future__ import annotations

from uuid import uuid4

from engine.core.ids import uuid7
from engine.learning.learner import (
    OutcomeObservation,
    fit_frozen_policy,
    in_canary_slice,
)
from engine.routing.policy import (
    PROFILE_GENERAL_IMPLEMENTATION,
    PROFILE_LONGCONTEXT_ECONOMY,
)


def _obs(
    *,
    workload_class: str = "bulk_implementation",
    profile: str = PROFILE_LONGCONTEXT_ECONOMY,
    success: bool = True,
    partition: str = "train",
) -> OutcomeObservation:
    return OutcomeObservation(
        experience_id=uuid7(),
        workload_class=workload_class,
        selected_profile_id=profile,
        success=success,
        holdout_partition=partition,  # type: ignore[arg-type]
    )


def test_cold_start_train_partition_is_refused_at_offline_evaluate() -> None:
    fit = fit_frozen_policy([_obs(partition="holdout")])
    assert fit.refused_reason == "offline_fit_cold_start"
    assert fit.mapping == {}
    assert fit.beats_constant_policy is False


def test_frozen_fit_selects_higher_success_profile_per_class() -> None:
    train = [
        _obs(profile=PROFILE_LONGCONTEXT_ECONOMY, success=False),
        _obs(profile=PROFILE_LONGCONTEXT_ECONOMY, success=False),
        _obs(profile=PROFILE_GENERAL_IMPLEMENTATION, success=True),
        _obs(profile=PROFILE_GENERAL_IMPLEMENTATION, success=True),
        _obs(profile=PROFILE_GENERAL_IMPLEMENTATION, success=True),
    ]
    holdout = [
        _obs(profile=PROFILE_GENERAL_IMPLEMENTATION, success=True, partition="holdout"),
        _obs(profile=PROFILE_LONGCONTEXT_ECONOMY, success=False, partition="holdout"),
    ]
    fit = fit_frozen_policy(train + holdout)
    assert fit.refused_reason is None
    assert fit.fit_kind == "frozen_full_information"
    assert fit.mapping["bulk_implementation"] == PROFILE_GENERAL_IMPLEMENTATION
    assert fit.constant_policy_profile_id == PROFILE_GENERAL_IMPLEMENTATION
    assert fit.beats_constant_policy is False
    assert fit.brier is not None
    assert fit.ece is not None


def test_learner_beats_constant_when_class_conditional_wins() -> None:
    """Two classes, two arms: each arm is best on one class. A constant
    policy cannot match the class-conditional expected reward."""
    runner = "profile.deterministic_runner"
    train = [
        *[
            _obs(profile=PROFILE_GENERAL_IMPLEMENTATION, success=True)
            for _ in range(19)
        ],
        _obs(profile=PROFILE_GENERAL_IMPLEMENTATION, success=False),
        *[
            _obs(workload_class="verification", profile=runner, success=True)
            for _ in range(8)
        ],
        *[
            _obs(workload_class="verification", profile=runner, success=False)
            for _ in range(2)
        ],
        *[
            _obs(
                workload_class="verification",
                profile=PROFILE_GENERAL_IMPLEMENTATION,
                success=True,
            )
            for _ in range(5)
        ],
        *[
            _obs(
                workload_class="verification",
                profile=PROFILE_GENERAL_IMPLEMENTATION,
                success=False,
            )
            for _ in range(5)
        ],
    ]
    holdout = [
        _obs(profile=PROFILE_GENERAL_IMPLEMENTATION, success=True, partition="holdout"),
        _obs(
            workload_class="verification",
            profile=runner,
            success=True,
            partition="holdout",
        ),
    ]
    fit = fit_frozen_policy(train + holdout)
    assert fit.mapping["bulk_implementation"] == PROFILE_GENERAL_IMPLEMENTATION
    assert fit.mapping["verification"] == runner
    assert fit.holdout_learner_expected is not None
    assert fit.holdout_constant_expected is not None
    assert fit.holdout_learner_expected > fit.holdout_constant_expected
    assert fit.beats_constant_policy is True


def test_canary_slice_is_hash_stable_and_fraction_zero_never_assigns() -> None:
    task_id = uuid4()
    assert in_canary_slice(task_id, 0.0) is False
    assert in_canary_slice(task_id, 1.0) is True
    first = in_canary_slice(task_id, 0.5)
    second = in_canary_slice(task_id, 0.5)
    assert first is second
