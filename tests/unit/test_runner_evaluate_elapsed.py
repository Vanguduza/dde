"""Mid-band confidence semantics and the elapsed control over
`engine.verification.runner._evaluate` -- the production verdict function.

Pure policy tests: no PostgreSQL, no subprocess. They pin (1) the exact
band boundaries and their downstream meaning as already consumed by the
recovery matrix and Chapter 6.5 telemetry (both read status/failure-class,
never mid-band values), (2) the declared penalty constants, (3) the
degrade-only guarantee: the elapsed control deepens a PARTIAL value or is
silent, never demoting PASSED or lifting FAILED.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from engine.contracts.verification_run import ObservableOutcomeResult
from engine.verification.runner import (
    CHECK_TIMEOUT_MS,
    ELAPSED_DEGRADE_ONSET_FRACTION,
    ELAPSED_PENALTY_MAX_FRACTION,
    _elapsed_penalty_factor,
    _evaluate,
    _excess_elapsed_pressure,
)

_ONSET_MS = int(CHECK_TIMEOUT_MS * ELAPSED_DEGRADE_ONSET_FRACTION)


def _result(status: str) -> ObservableOutcomeResult:
    return ObservableOutcomeResult(
        outcome_id=uuid4(),
        statement="suite passes",
        is_negative_case=False,
        check_ref="tests/test_x.py",
        status=status,
        evaluated_at=datetime.now(UTC),
    )


def test_constants_are_declared_and_in_range() -> None:
    """The penalty's only knobs are module constants: onset inside (0, 1),
    maximum haircut inside [0, 1), ceiling tied to the real check-runner
    default timeout."""
    assert CHECK_TIMEOUT_MS == 120_000.0
    assert 0.0 < ELAPSED_DEGRADE_ONSET_FRACTION < 1.0
    assert 0.0 <= ELAPSED_PENALTY_MAX_FRACTION < 1.0


def test_pressure_is_zero_up_to_onset_and_one_at_deadline() -> None:
    """The pressure ramp: flat zero at/below the onset point, linear across
    the onset..deadline span, capped at 1.0 AT the deadline; negative
    durations clamp to zero."""

    def at(ms: int) -> float:
        return _excess_elapsed_pressure(
            ms,
            timeout_ms=CHECK_TIMEOUT_MS,
            onset_fraction=ELAPSED_DEGRADE_ONSET_FRACTION,
        )

    quarter = int(CHECK_TIMEOUT_MS * 0.25)
    half = int(CHECK_TIMEOUT_MS * 0.5)
    eighth_over = int(_ONSET_MS + CHECK_TIMEOUT_MS * 0.1)
    assert at(-1) == 0.0
    assert at(0) == 0.0
    assert at(quarter) == 0.0
    assert at(half) == 0.0
    assert at(_ONSET_MS) == 0.0
    assert 0.0 < at(eighth_over) <= 1.0
    assert at(int(CHECK_TIMEOUT_MS)) == 1.0
    assert at(int(CHECK_TIMEOUT_MS * 10)) == 1.0


def test_penalty_factor_bounds_and_no_data_neutral() -> None:
    """No timing data leaves the factor exactly neutral (absence of
    evidence never moves a verdict); with data it stays within
    [1 - max_haircut, 1]."""
    neutral = _elapsed_penalty_factor(
        [],
        timeout_ms=CHECK_TIMEOUT_MS,
        onset_fraction=ELAPSED_DEGRADE_ONSET_FRACTION,
        max_penalty_fraction=ELAPSED_PENALTY_MAX_FRACTION,
    )
    floor = 1.0 - ELAPSED_PENALTY_MAX_FRACTION
    snappy = _elapsed_penalty_factor(
        [_ONSET_MS],
        timeout_ms=CHECK_TIMEOUT_MS,
        onset_fraction=ELAPSED_DEGRADE_ONSET_FRACTION,
        max_penalty_fraction=ELAPSED_PENALTY_MAX_FRACTION,
    )
    maxed = _elapsed_penalty_factor(
        [int(CHECK_TIMEOUT_MS)],
        timeout_ms=CHECK_TIMEOUT_MS,
        onset_fraction=ELAPSED_DEGRADE_ONSET_FRACTION,
        max_penalty_fraction=ELAPSED_PENALTY_MAX_FRACTION,
    )
    mixed = _elapsed_penalty_factor(
        [100, int(CHECK_TIMEOUT_MS)],
        timeout_ms=CHECK_TIMEOUT_MS,
        onset_fraction=ELAPSED_DEGRADE_ONSET_FRACTION,
        max_penalty_fraction=ELAPSED_PENALTY_MAX_FRACTION,
    )
    assert neutral == 1.0
    assert snappy == 1.0
    assert floor <= mixed <= 1.0
    assert maxed == floor


def test_certified_pass_band_is_exact() -> None:
    """Band 1.0: every outcome holds -> PASSED at exactly the raw ratio;
    the elapsed control cannot erode a certified value even when every
    check ran to its deadline."""
    results = [_result("PASSED"), _result("PASSED")]
    status, confidence = _evaluate(
        outcome_results=results,
        negative_results=[],
        minimum_confidence=1.0,
        check_durations_ms=[int(CHECK_TIMEOUT_MS), int(CHECK_TIMEOUT_MS)],
    )
    assert status == "PASSED"
    assert confidence == 1.0


def test_zero_band_stays_failed_at_raw_ratio() -> None:
    """Band 0.0: nothing holds -> FAILED at exactly 0.0; the elapsed
    control never lifts a failing set."""
    status, confidence = _evaluate(
        outcome_results=[_result("FAILED")],
        negative_results=[],
        minimum_confidence=0.5,
        check_durations_ms=[int(CHECK_TIMEOUT_MS)],
    )
    assert status == "FAILED"
    assert confidence == 0.0


def test_mid_band_high_water_vs_low_water_semantics() -> None:
    """PARTIAL is graded: majority-held outcomes land above the 0.5
    high-water mark (near-pass), minority-held below it (near-fail);
    both stay PARTIAL with their raw ratios when checks are snappy."""
    high_status, high_confidence = _evaluate(
        outcome_results=[_result("PASSED"), _result("PASSED"), _result("FAILED")],
        negative_results=[],
        minimum_confidence=1.0,
        check_durations_ms=[100, 100, 100],
    )
    low_status, low_confidence = _evaluate(
        outcome_results=[_result("PASSED"), _result("FAILED"), _result("FAILED")],
        negative_results=[],
        minimum_confidence=1.0,
        check_durations_ms=[100, 100, 100],
    )
    boundary_status, boundary_confidence = _evaluate(
        outcome_results=[_result("PASSED"), _result("FAILED")],
        negative_results=[],
        minimum_confidence=1.0,
        check_durations_ms=[100, 100],
    )
    assert (high_status, high_confidence) == ("PARTIAL", 2 / 3)
    assert (low_status, low_confidence) == ("PARTIAL", 1 / 3)
    assert (boundary_status, boundary_confidence) == ("PARTIAL", 0.5)


def test_elapsed_control_degrades_only_inside_mid_band() -> None:
    """Every check at its full deadline: the certified pass keeps 1.0, the
    failing set stays FAILED/0.0, and ONLY the mid-band value is eroded --
    toward zero, never past it, and strictly below the raw ratio."""
    passing = [_result("PASSED"), _result("PASSED")]
    failing = [_result("FAILED"), _result("FAILED")]
    mixed = [_result("PASSED"), _result("FAILED")]
    deadline_ms = [int(CHECK_TIMEOUT_MS)] * 2
    passed_status, passed_confidence = _evaluate(
        outcome_results=passing,
        negative_results=[],
        minimum_confidence=1.0,
        check_durations_ms=deadline_ms,
    )
    failed_status, failed_confidence = _evaluate(
        outcome_results=failing,
        negative_results=[],
        minimum_confidence=0.5,
        check_durations_ms=deadline_ms,
    )
    partial_status, partial_confidence = _evaluate(
        outcome_results=mixed,
        negative_results=[],
        minimum_confidence=1.0,
        check_durations_ms=deadline_ms,
    )
    assert (passed_status, passed_confidence) == ("PASSED", 1.0)
    assert (failed_status, failed_confidence) == ("FAILED", 0.0)
    assert partial_status == "PARTIAL"
    assert partial_confidence == 0.25
    assert partial_confidence < 0.5


def test_elapsed_control_cannot_flip_a_verdict() -> None:
    """A high-water PARTIAL degraded by the elapsed haircut must remain
    PARTIAL -- bands key on the raw ratio, so erosion moves only the
    persisted value, strictly deeper into the band toward zero."""
    raw_ratio = 3 / 4
    status, confidence = _evaluate(
        outcome_results=[
            _result("PASSED"),
            _result("PASSED"),
            _result("PASSED"),
            _result("FAILED"),
        ],
        negative_results=[],
        minimum_confidence=1.0,
        check_durations_ms=[int(CHECK_TIMEOUT_MS)] * 4,
    )
    assert status == "PARTIAL"
    assert confidence == 0.375
    assert 0.0 < confidence < raw_ratio


def test_snappy_checks_leave_mid_band_bit_identical() -> None:
    """Durations at/below the onset point are penalty-free: the persisted
    PARTIAL value equals the raw ratio exactly (no float drift)."""
    status, confidence = _evaluate(
        outcome_results=[_result("PASSED"), _result("FAILED")],
        negative_results=[],
        minimum_confidence=1.0,
        check_durations_ms=[_ONSET_MS, 1],
    )
    no_data_status, no_data_confidence = _evaluate(
        outcome_results=[_result("PASSED"), _result("FAILED")],
        negative_results=[],
        minimum_confidence=1.0,
    )
    assert (status, confidence) == ("PARTIAL", 0.5)
    assert (no_data_status, no_data_confidence) == ("PARTIAL", 0.5)


def test_negative_cases_count_in_the_same_band() -> None:
    """Negative cases join the ratio mechanically: an outcome holding plus
    a negative case NOT holding (both PASSED statuses) is still a
    certified 1.0 pass; one violated negative case lands mid-band."""
    held = [_result("PASSED")]
    not_held = [_result("PASSED")]
    violated = [_result("FAILED")]
    ok = _evaluate(
        outcome_results=held, negative_results=not_held, minimum_confidence=1.0
    )
    bad = _evaluate(
        outcome_results=held,
        negative_results=violated,
        minimum_confidence=1.0,
        check_durations_ms=[100, 100],
    )
    assert ok == ("PASSED", 1.0)
    assert bad[0] == "PARTIAL"
    assert bad[1] == 0.5
