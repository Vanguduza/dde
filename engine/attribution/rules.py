"""Chapter 5.11 deterministic rule set -- runs first, before any model
judgment fallback.

Chapter 5.11 names three deterministic checks: "was a required category
`partial`? did the worker request context that existed but was not
supplied? did it edit outside the supplied scope?" This Stage 1 slice
implements two of the three for real, against already-persisted or
directly-observable production signals:

1. **required-category-partial** -- reads the real, persisted
   `ContextPackage.coverage` JSON for the task (Chapter 5.8's coverage
   contract, computed by `engine.context.coverage.compute_coverage` at
   context-compile time, not re-derived or guessed here).
2. **edited-outside-supplied-scope** -- reads the real set of paths that
   differ between the `Workspace`'s `base_revision` and its current state
   (`engine.workspaces.git.diff_name_only`, committed and uncommitted),
   compared against the `Task`'s real `expected_write_scope` via
   `engine.context.repo.touches_scope` -- the same scope-membership test
   `engine.context.coverage` itself uses.

The third, **context-request-denied**, needs Chapter 5.12's just-in-time
expansion (`ContextRequest`/`ContextResponse`); no writer in this codebase
produces that data yet, so this rule cannot be evaluated for real. It is
named in `rule_reasons` as a disclosed gap on every attribution, never
silently treated as "no" evidence.

No model-judgment fallback is implemented here -- the same no-model-call
constraint `engine.context.critic`/`engine.context.conflict` document for
Stage 1 core control-plane code. An outcome the deterministic rules cannot
resolve is reported honestly as `inconclusive`, with
`eligible_for_promotion_gating=False` (Chapter 5.11: "only [rule-derived
attributions] are eligible to gate policy promotion" -- an inconclusive
verdict is not rule-derived evidence either way, so it does not qualify).

Rule precedence, evaluated in the blueprint's own listed order: a
required-category miss is treated as sufficient, on-its-own evidence of
context omission regardless of what the scope check would say (Chapter
5.11 lists it first); scope overreach is evaluated only when the coverage
check found nothing, and is treated as evidence *against* context
attribution (a worker that had adequate context but edited beyond its
declared scope is a worker/competence signal, not a context-supply one)
-- a Stage 1 approximation of causal disambiguation that a real model
judgment would otherwise resolve, flagged as such rather than presented as
the blueprint's own reasoning.
"""

from __future__ import annotations

from engine.attribution.model import REQUIRED_COVERAGE_CATEGORIES, AttributionResult
from engine.context.repo import touches_scope

CONTEXT_REQUEST_RULE_DEFERRED = (
    "context_request_denied rule deferred: Chapter 5.12 just-in-time "
    "expansion (ContextRequest/ContextResponse) is not implemented in this "
    "codebase yet, so 'did the worker request context that existed but was "
    "not supplied' cannot be evaluated for real -- disclosed gap, not a "
    "silent 'no'."
)

MODEL_JUDGMENT_NOT_IMPLEMENTED = (
    "no deterministic rule fired; Chapter 5.11's model-judgment fallback is "
    "not implemented in this codebase (Stage 1 gap, disclosed) -- reported "
    "as inconclusive rather than silently defaulting to a verdict."
)


def attribute_failure(
    *,
    coverage: dict[str, object] | None,
    expected_write_scope: list[str],
    changed_paths: list[str],
) -> AttributionResult:
    """Chapter 5.11: "Attribution is produced by a deterministic rule set
    first ... and only falls back to a model judgment when the rules are
    inconclusive." Every condition considered is recorded in
    `rule_reasons`, including the ones that did not fire and the ones this
    Stage 1 slice cannot evaluate at all -- a reader of one row never has
    to cross-reference this module to know what was and was not checked.
    """
    reasons: list[str] = []

    partial_categories = _partial_required_categories(coverage)
    if partial_categories:
        reasons.append(
            "required_category_partial_or_missing:" + ",".join(partial_categories)
        )
        reasons.append(CONTEXT_REQUEST_RULE_DEFERRED)
        return AttributionResult(
            outcome="context_attributed",
            category="context_omission",
            method="rule_based",
            rule_reasons=tuple(reasons),
            confidence=1.0,
            eligible_for_promotion_gating=True,
            excluded_from_routing_learning=True,
        )

    reasons.append(CONTEXT_REQUEST_RULE_DEFERRED)

    overreach = _paths_outside_scope(changed_paths, expected_write_scope)
    if overreach:
        reasons.append("edited_outside_supplied_scope:" + ",".join(sorted(overreach)))
        return AttributionResult(
            outcome="not_context_attributed",
            category="none",
            method="rule_based",
            rule_reasons=tuple(reasons),
            confidence=1.0,
            eligible_for_promotion_gating=True,
            excluded_from_routing_learning=False,
        )

    reasons.append(MODEL_JUDGMENT_NOT_IMPLEMENTED)
    return AttributionResult(
        outcome="inconclusive",
        category="none",
        method="rule_based",
        rule_reasons=tuple(reasons),
        confidence=0.0,
        eligible_for_promotion_gating=False,
        excluded_from_routing_learning=False,
    )


def _partial_required_categories(coverage: dict[str, object] | None) -> list[str]:
    if not coverage:
        return []
    return sorted(
        category
        for category in REQUIRED_COVERAGE_CATEGORIES
        if coverage.get(category) in ("partial", "missing")
    )


def _paths_outside_scope(
    changed_paths: list[str], expected_write_scope: list[str]
) -> list[str]:
    if not expected_write_scope or not changed_paths:
        return []
    scope = tuple(expected_write_scope)
    return [path for path in changed_paths if not touches_scope(path, scope)]
