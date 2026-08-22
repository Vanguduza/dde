"""In-process value objects for the Chapter 5.11 failure-attribution
engine (DDE-034).

`schemas/objects/failure_attribution.json` is the durable contract this
module owns (Chapter 3.8); `AttributionResult` is the pure rule-evaluation
output before it is stamped with identity and persisted as a
`FailureAttribution` row.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Chapter 5.8 coverage-contract categories a `CoverageReport` always
#: names (`engine.context.model.CoverageReport.required_statuses()`),
#: mirrored here rather than imported so `engine.attribution` does not
#: need a compile-time dependency on `engine.context`'s dataclasses --
#: only on the already-persisted `ContextPackage.coverage` JSON blob.
REQUIRED_COVERAGE_CATEGORIES = (
    "authoritative_requirements",
    "applicable_domain_rules",
    "impacted_code_and_deps",
    "architecture_constraints",
    "security_constraints",
    "verification_obligations",
)


@dataclass(frozen=True)
class AttributionResult:
    """One deterministic-rule verdict, before persistence."""

    outcome: str
    category: str
    method: str
    rule_reasons: tuple[str, ...]
    confidence: float
    eligible_for_promotion_gating: bool
    excluded_from_routing_learning: bool
