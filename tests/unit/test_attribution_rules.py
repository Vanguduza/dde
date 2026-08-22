"""Chapter 5.11 deterministic rule set: pure, input-dependent verdicts
over real signal shapes -- `engine.attribution.rules`."""

from __future__ import annotations

from engine.attribution.rules import (
    CONTEXT_REQUEST_RULE_DEFERRED,
    MODEL_JUDGMENT_NOT_IMPLEMENTED,
    attribute_failure,
)

_FULL_COVERAGE = {
    "authoritative_requirements": "satisfied",
    "applicable_domain_rules": "satisfied",
    "impacted_code_and_deps": "satisfied",
    "architecture_constraints": "satisfied",
    "security_constraints": "satisfied",
    "verification_obligations": "satisfied",
}


def test_partial_required_category_attributes_to_context_omission() -> None:
    coverage = {**_FULL_COVERAGE, "impacted_code_and_deps": "partial"}

    result = attribute_failure(
        coverage=coverage, expected_write_scope=[], changed_paths=[]
    )

    assert result.outcome == "context_attributed"
    assert result.category == "context_omission"
    assert result.method == "rule_based"
    assert result.eligible_for_promotion_gating is True
    assert result.excluded_from_routing_learning is True
    assert any("impacted_code_and_deps" in reason for reason in result.rule_reasons)


def test_missing_required_category_attributes_to_context_omission() -> None:
    coverage = {**_FULL_COVERAGE, "security_constraints": "missing"}

    result = attribute_failure(
        coverage=coverage, expected_write_scope=[], changed_paths=[]
    )

    assert result.outcome == "context_attributed"
    assert result.category == "context_omission"


def test_edit_outside_scope_with_full_coverage_is_not_context_attributed() -> None:
    result = attribute_failure(
        coverage=_FULL_COVERAGE,
        expected_write_scope=["engine/widgets"],
        changed_paths=["engine/other/service.py"],
    )

    assert result.outcome == "not_context_attributed"
    assert result.category == "none"
    assert result.eligible_for_promotion_gating is True
    assert result.excluded_from_routing_learning is False
    assert any(
        "edited_outside_supplied_scope" in reason for reason in result.rule_reasons
    )


def test_edits_within_scope_with_full_coverage_is_inconclusive() -> None:
    result = attribute_failure(
        coverage=_FULL_COVERAGE,
        expected_write_scope=["engine/widgets"],
        changed_paths=["engine/widgets/service.py"],
    )

    assert result.outcome == "inconclusive"
    assert result.category == "none"
    assert result.eligible_for_promotion_gating is False
    assert result.excluded_from_routing_learning is False
    assert MODEL_JUDGMENT_NOT_IMPLEMENTED in result.rule_reasons


def test_no_coverage_and_no_scope_is_inconclusive_not_a_fabricated_verdict() -> None:
    result = attribute_failure(coverage=None, expected_write_scope=[], changed_paths=[])

    assert result.outcome == "inconclusive"
    assert result.method == "rule_based"


def test_coverage_partial_takes_precedence_over_scope_overreach() -> None:
    """Chapter 5.11 lists the coverage-partial check first; a genuine
    coverage gap is treated as sufficient evidence on its own, even when
    the same failure also shows scope overreach."""
    coverage = {**_FULL_COVERAGE, "architecture_constraints": "partial"}

    result = attribute_failure(
        coverage=coverage,
        expected_write_scope=["engine/widgets"],
        changed_paths=["engine/other/service.py"],
    )

    assert result.outcome == "context_attributed"
    assert result.category == "context_omission"


def test_context_request_rule_gap_is_always_disclosed() -> None:
    result = attribute_failure(
        coverage=_FULL_COVERAGE, expected_write_scope=[], changed_paths=[]
    )

    assert CONTEXT_REQUEST_RULE_DEFERRED in result.rule_reasons
