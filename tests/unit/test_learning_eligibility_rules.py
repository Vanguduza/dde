"""Chapter 6.8 eligibility filter: pure, input-dependent verdicts over
real signal shapes -- `engine.learning.rules`.

These tests exist so the four Chapter 6.8 conditions (and the Chapter
6.5 flaky-quarantine amendment) fail closed before any PostgreSQL writer
exists. A later mission that widens eligibility to make a learner pass
has to change these tests, not a docstring.
"""

from __future__ import annotations

from uuid import UUID

from engine.learning.model import (
    ATTRIBUTION_DOWN_WEIGHTED,
    ATTRIBUTION_EXCLUDED_PREFIX,
    CONFIDENCE_REASON,
    FLAKY_QUARANTINE_REASON,
    NOT_TERMINAL_REASON,
    SIMULATION_ORIGIN_REASON,
)
from engine.learning.rules import (
    evaluate_eligibility,
    holdout_partition,
    map_failure_attribution,
)


def test_passed_real_terminal_record_is_eligible() -> None:
    verdict = evaluate_eligibility(
        experience_origin="real",
        verification_confidence=1.0,
        failure_attribution="none",
        attribution_confidence=1.0,
        terminal=True,
        flaky_quarantined=False,
    )
    assert verdict.eligible_for_routing_training is True
    assert verdict.down_weighted is False
    assert verdict.failure_attribution == "none"
    assert "eligible" in verdict.reasons


def test_route_attributable_failure_is_eligible() -> None:
    verdict = evaluate_eligibility(
        experience_origin="real",
        verification_confidence=1.0,
        failure_attribution="route_attributable",
        attribution_confidence=1.0,
        terminal=True,
        flaky_quarantined=False,
    )
    assert verdict.eligible_for_routing_training is True
    assert verdict.down_weighted is False


def test_simulation_origin_is_never_eligible() -> None:
    verdict = evaluate_eligibility(
        experience_origin="simulation",
        verification_confidence=1.0,
        failure_attribution="none",
        attribution_confidence=1.0,
        terminal=True,
        flaky_quarantined=False,
    )
    assert verdict.eligible_for_routing_training is False
    assert SIMULATION_ORIGIN_REASON in verdict.reasons


def test_low_verification_confidence_is_ineligible() -> None:
    verdict = evaluate_eligibility(
        experience_origin="real",
        verification_confidence=0.5,
        failure_attribution="none",
        attribution_confidence=1.0,
        terminal=True,
        flaky_quarantined=False,
    )
    assert verdict.eligible_for_routing_training is False
    assert CONFIDENCE_REASON in verdict.reasons


def test_context_attributed_failure_is_excluded() -> None:
    verdict = evaluate_eligibility(
        experience_origin="real",
        verification_confidence=1.0,
        failure_attribution="context",
        attribution_confidence=1.0,
        terminal=True,
        flaky_quarantined=False,
    )
    assert verdict.eligible_for_routing_training is False
    assert ATTRIBUTION_EXCLUDED_PREFIX + "context" in verdict.reasons
    assert verdict.down_weighted is False


def test_low_confidence_context_attribution_is_down_weighted_not_dropped() -> None:
    """Chapter 6.8: excluded attributions 'included with a down-weight
    only when attribution confidence is low and the record is flagged.'"""
    verdict = evaluate_eligibility(
        experience_origin="real",
        verification_confidence=1.0,
        failure_attribution="context",
        attribution_confidence=0.2,
        terminal=True,
        flaky_quarantined=False,
    )
    assert verdict.eligible_for_routing_training is True
    assert verdict.down_weighted is True
    assert ATTRIBUTION_DOWN_WEIGHTED in verdict.reasons


def test_inconclusive_high_confidence_is_excluded() -> None:
    verdict = evaluate_eligibility(
        experience_origin="real",
        verification_confidence=1.0,
        failure_attribution="inconclusive",
        attribution_confidence=1.0,
        terminal=True,
        flaky_quarantined=False,
    )
    assert verdict.eligible_for_routing_training is False
    assert ATTRIBUTION_EXCLUDED_PREFIX + "inconclusive" in verdict.reasons


def test_non_terminal_outcome_is_ineligible() -> None:
    verdict = evaluate_eligibility(
        experience_origin="real",
        verification_confidence=1.0,
        failure_attribution="none",
        attribution_confidence=1.0,
        terminal=False,
        flaky_quarantined=False,
    )
    assert verdict.eligible_for_routing_training is False
    assert NOT_TERMINAL_REASON in verdict.reasons


def test_flaky_quarantine_excludes_from_routing_learning() -> None:
    verdict = evaluate_eligibility(
        experience_origin="real",
        verification_confidence=1.0,
        failure_attribution="route_attributable",
        attribution_confidence=1.0,
        terminal=True,
        flaky_quarantined=True,
    )
    assert verdict.eligible_for_routing_training is False
    assert FLAKY_QUARANTINE_REASON in verdict.reasons


def test_environment_tool_spec_upstream_are_excluded() -> None:
    for klass in ("environment", "tool", "specification", "upstream"):
        verdict = evaluate_eligibility(
            experience_origin="real",
            verification_confidence=1.0,
            failure_attribution=klass,  # type: ignore[arg-type]
            attribution_confidence=1.0,
            terminal=True,
            flaky_quarantined=False,
        )
        assert verdict.eligible_for_routing_training is False
        assert ATTRIBUTION_EXCLUDED_PREFIX + klass in verdict.reasons


def test_map_passed_outcome_is_none() -> None:
    klass, confidence = map_failure_attribution(
        actual_verified_outcome="PASSED",
        attribution_outcome=None,
        attribution_confidence=None,
    )
    assert klass == "none"
    assert confidence == 1.0


def test_map_not_context_attributed_is_route_attributable() -> None:
    klass, confidence = map_failure_attribution(
        actual_verified_outcome="FAILED",
        attribution_outcome="not_context_attributed",
        attribution_confidence=1.0,
    )
    assert klass == "route_attributable"
    assert confidence == 1.0


def test_map_context_attributed() -> None:
    klass, _ = map_failure_attribution(
        actual_verified_outcome="FAILED",
        attribution_outcome="context_attributed",
        attribution_confidence=1.0,
    )
    assert klass == "context"


def test_map_inconclusive() -> None:
    klass, confidence = map_failure_attribution(
        actual_verified_outcome="FAILED",
        attribution_outcome="inconclusive",
        attribution_confidence=0.0,
    )
    assert klass == "inconclusive"
    assert confidence == 0.0


def test_holdout_partition_is_deterministic_and_hashed() -> None:
    experience_id = UUID("00000000-0000-0000-0000-000000000001")
    first = holdout_partition(experience_id)
    second = holdout_partition(experience_id)
    assert first == second
    assert first in ("train", "holdout")
    # Adjacent UUID7-shaped ids must not collapse to one partition just
    # because their timestamps match -- hashing is the load-bearing bit.
    nearby = UUID("00000000-0000-0000-0000-000000000002")
    samples = {holdout_partition(experience_id), holdout_partition(nearby)}
    assert samples <= {"train", "holdout"}
