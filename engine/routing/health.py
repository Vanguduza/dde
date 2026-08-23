"""Model health from recorded `routing_decision_outcomes` (adoption #4).

Pure computation over outcome rows -- the same Chapter 6.5 rows shadow
promotion replays. A profile is *healthy* until its rolling failure rate
over the observation window breaches ``max_failure_rate``; elapsed seconds
are reported alongside as a regression signal but never evict on their
own. Outcome rows carry no profile column, so callers join each row to
its RouteDecision's ``selected_worker_profile_id`` and hand over
:class:`HealthSample`s.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from engine.contracts.routing_decision_outcome import RoutingDecisionOutcome

#: Only the most recent N outcomes per profile are evaluated; older rows
#: age out of the window regardless of wall-clock distance.
DEFAULT_HEALTH_WINDOW_SIZE = 10
#: Breaching this failure rate over the window marks a profile unhealthy.
DEFAULT_MAX_FAILURE_RATE = 0.6
#: Below this many samples in the window there is no verdict at all --
#: an unproven profile is never evicted on suspicion.
DEFAULT_MIN_SAMPLES = 3


@dataclass(frozen=True)
class HealthThresholds:
    """Configurable knobs for :func:`compute_model_health`.

    Defaults come from this module's constants so policy tables can stay
    silent; a routing policy may override them explicitly.
    """

    window_size: int = DEFAULT_HEALTH_WINDOW_SIZE
    max_failure_rate: float = DEFAULT_MAX_FAILURE_RATE
    min_samples: int = DEFAULT_MIN_SAMPLES


@dataclass(frozen=True)
class HealthSample:
    """One attributed outcome: a profile produced a verified result."""

    worker_profile_id: str
    failed: bool
    elapsed_seconds: float | None = None


@dataclass(frozen=True)
class ProfileHealth:
    """Rolling health verdict for one worker profile."""

    worker_profile_id: str
    sample_count: int = 0
    failure_count: int = 0
    failure_rate: float = 0.0
    mean_elapsed_seconds: float | None = None
    healthy: bool = True


@dataclass(frozen=True)
class ModelHealthReport:
    """Per-profile verdicts plus the set the router must exclude."""

    thresholds: HealthThresholds
    profiles: dict[str, ProfileHealth] = field(default_factory=dict)

    def unhealthy_profiles(self) -> frozenset[str]:
        """Profiles whose breach evicts them from selection.

        Profiles with no outcomes at all are absent from ``profiles``
        entirely and therefore never excluded here: absence of evidence
        is not unhealthiness.
        """

        return frozenset(
            profile_id
            for profile_id, health in self.profiles.items()
            if not health.healthy
        )


def health_samples_from_outcomes(
    outcomes_with_profiles: Iterable[tuple[RoutingDecisionOutcome, str | None]],
) -> list[HealthSample]:
    """Project joined (outcome, selected profile id) rows onto samples.

    Rows whose RouteDecision carries no profile id cannot be attributed
    and are skipped; failure is ``actual_verified_outcome != "PASSED"``
    -- the same ground truth axis shadow promotion replays against.
    """

    samples: list[HealthSample] = []
    for outcome, profile_id in outcomes_with_profiles:
        if not profile_id:
            continue
        elapsed = (
            float(outcome.elapsed_seconds)
            if outcome.elapsed_seconds is not None
            else None
        )
        samples.append(
            HealthSample(
                worker_profile_id=profile_id,
                failed=outcome.actual_verified_outcome != "PASSED",
                elapsed_seconds=elapsed,
            )
        )
    return samples


def _latest_per_profile(
    samples: Iterable[HealthSample],
    window_size: int,
) -> dict[str, list[HealthSample]]:
    """Keep only the newest ``window_size`` samples per profile.

    Input order is oldest-first (repository read order); the last
    ``window_size`` samples seen per profile are the effective window.
    """

    windows: dict[str, list[HealthSample]] = defaultdict(list)
    for sample in samples:
        bucket = windows[sample.worker_profile_id]
        bucket.append(sample)
        overflow = len(bucket) - window_size
        if overflow > 0:
            del bucket[:overflow]
    return dict(windows)


def compute_model_health(
    samples: Sequence[HealthSample],
    thresholds: HealthThresholds | None = None,
) -> ModelHealthReport:
    """Compute rolling health per profile over attributed samples."""

    limits = thresholds or HealthThresholds()
    report = ModelHealthReport(thresholds=limits)
    for profile_id, rows in _latest_per_profile(
        samples, max(limits.window_size, 1)
    ).items():
        failures = sum(1 for sample in rows if sample.failed)
        elapsed_values = [
            sample.elapsed_seconds
            for sample in rows
            if sample.elapsed_seconds is not None
        ]
        mean_elapsed = (
            sum(elapsed_values) / len(elapsed_values) if elapsed_values else None
        )
        rate = failures / len(rows)
        healthy = (
            len(rows) >= limits.min_samples and rate <= limits.max_failure_rate
        ) or len(rows) < limits.min_samples
        report.profiles[profile_id] = ProfileHealth(
            worker_profile_id=profile_id,
            sample_count=len(rows),
            failure_count=failures,
            failure_rate=rate,
            mean_elapsed_seconds=mean_elapsed,
            healthy=healthy,
        )
    return report


def thresholds_from_policy_overrides(
    policy_overrides: Mapping[str, object] | None,
) -> HealthThresholds:
    """Project routing-policy keys onto health thresholds.

    Unknown keys are ignored so the same overrides mapping can carry
    other policy settings.
    """

    defaults = HealthThresholds()
    if not policy_overrides:
        return defaults
    window = policy_overrides.get("health_window_size")
    rate = policy_overrides.get("health_max_failure_rate")
    floor = policy_overrides.get("health_min_samples")
    return HealthThresholds(
        window_size=(
            int(window)  # type: ignore[call-overload]
            if window is not None
            else defaults.window_size
        ),
        max_failure_rate=(
            float(rate)  # type: ignore[arg-type]
            if rate is not None
            else defaults.max_failure_rate
        ),
        min_samples=(
            int(floor)  # type: ignore[call-overload]
            if floor is not None
            else defaults.min_samples
        ),
    )
