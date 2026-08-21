"""Chapter 5.9 Context Critic -- triggered, not default.

Trigger evaluation runs over signals `ContextService.compile()` already
computes for other reasons: the Task's own `risk_class`/`blast_radius`
(Chapter 4), the Chapter 5.8 coverage contract, and a real (if Stage-1-
approximate) confidence signal derived from what the Chapter 5.2
retrievers actually returned. Chapter 5.9's five conditions, and how each
is evaluated here:

1. ``risk_class >= high`` -- direct from `Task.risk_class`.
2. ``blast_radius >= cross_module`` -- direct from `Task.blast_radius`.
3. coverage contains ``partial`` on a required category -- direct from
   the Chapter 5.8 `CoverageReport`.
4. "the task is a repair of a previously context-attributed failure" --
   Chapter 5.11's failure-attribution pipeline (the source of truth for
   "context-attributed") is not built anywhere in this codebase yet (no
   `engine.context` or `engine.execution` module records that a failure
   was attributed to context omission/contradiction/staleness/
   contamination/mis-ranking). `compile()` cannot honestly claim a `True`
   here on its own authority, so this condition takes an explicit
   `previously_context_attributed_failure` parameter that only a caller
   holding real Chapter 5.11 attribution data can set; it defaults to
   `False` because no caller in this codebase has that data source today.
   This is a deliberate, documented Stage 1 gap, not a silent drop of the
   condition -- see `docs/planning/mission-numbering-note.md`.
5. "confidence is below the policy threshold" -- Stage 1 has no separate
   `confidence` concept anywhere in `ContextItem`/`FusedItem`; the nearest
   real, already-computed signal is `ContextItem.relevance` (each Chapter
   5.2 retriever sets it from genuine match strength, not a constant --
   see e.g. `engine.context.retrievers.lexical`). `_mean_relevance` over
   the assembled, included item set is used as the Stage 1 confidence
   proxy, flagged as such rather than presented as the blueprint's own
   (unnamed) confidence metric.

Once triggered, the critic "may only request additional retrieval or
raise a Context Finding. It cannot alter Project Truth and cannot approve
its own request" (Chapter 5.9). Stage 1 has no separate retrieval
mechanism the critic can invoke on its own (that would mean the critic
running a second reasoning pass with a model call, which this module
deliberately does not make -- same constraint as `engine.context.
conflict`). What it *can* do honestly, deterministically, and for free is
look at what the Chapter 5.7 eviction pass already fused but dropped: if
evidence for a `partial` category exists in `AssembledContext.evicted`
and re-including it fits the budget, that is a real "additional
retrieval" request the critic can grant to itself for evicted-but-already
-retrieved evidence (not new content) without altering Project Truth or
needing to reason about anything new. If no such evidence exists, or
recovering it would blow the budget, the critic raises a Context Finding
instead -- it never silently upgrades a `partial`/`missing` coverage
category on its own authority.
"""

from __future__ import annotations

from engine.context.model import (
    AssembledContext,
    CoverageReport,
    CriticOutcome,
    CriticTriggerResult,
)
from engine.contracts.task import Task

RISK_CLASS_ORDER = ("low", "medium", "high", "critical")
BLAST_RADIUS_ORDER = ("none", "local", "module", "cross_module", "systemic")

DEFAULT_CRITIC_CONFIDENCE_THRESHOLD = 0.5
#: Fixed Stage 1 cost floor for a critic pass that examines zero evicted
#: items (e.g. missing, not merely evicted, evidence) -- Chapter 16.4
#: still counts the pass itself against the control-plane overhead
#: budget, not only the tokens it recovers.
CRITIC_BASE_COST_TOKENS = 50


def _at_least(value: str, order: tuple[str, ...], threshold: str) -> bool:
    return order.index(value) >= order.index(threshold)


def _mean_relevance(assembled: AssembledContext) -> float:
    if not assembled.included:
        return 0.0
    return sum(fused.item.relevance for fused in assembled.included) / len(
        assembled.included
    )


def evaluate_trigger(
    *,
    task: Task,
    coverage: CoverageReport,
    assembled: AssembledContext,
    confidence_threshold: float = DEFAULT_CRITIC_CONFIDENCE_THRESHOLD,
    previously_context_attributed_failure: bool = False,
) -> CriticTriggerResult:
    """Chapter 5.9: "runs when *any* holds" -- every condition is checked,
    not short-circuited, so `reasons` names every condition that fired."""
    reasons: list[str] = []
    if _at_least(task.risk_class, RISK_CLASS_ORDER, "high"):
        reasons.append("risk_class_high_or_above")
    if _at_least(task.blast_radius, BLAST_RADIUS_ORDER, "cross_module"):
        reasons.append("blast_radius_cross_module_or_above")
    partial_categories = sorted(
        category
        for category, status in coverage.required_statuses().items()
        if status == "partial"
    )
    if partial_categories:
        reasons.append("coverage_partial:" + ",".join(partial_categories))
    if task.task_class == "repair" and previously_context_attributed_failure:
        reasons.append("repair_of_context_attributed_failure")
    confidence = _mean_relevance(assembled)
    if confidence < confidence_threshold:
        reasons.append(
            f"confidence_below_threshold:{confidence:.2f}<{confidence_threshold:.2f}"
        )
    return CriticTriggerResult(
        triggered=bool(reasons), reasons=tuple(reasons), confidence=confidence
    )


def run_critic(
    *,
    coverage: CoverageReport,
    assembled: AssembledContext,
    budget_tokens: int,
) -> CriticOutcome:
    partial_categories = sorted(
        category
        for category, status in coverage.required_statuses().items()
        if status == "partial"
    )
    candidates = [
        fused
        for fused in assembled.evicted
        if any(category in fused.item.categories for category in partial_categories)
    ]
    if not candidates:
        return CriticOutcome(
            action="raised_finding",
            reassembled=None,
            outcome_summary=(
                "Triggered on "
                + (", ".join(partial_categories) or "a Chapter 5.9 condition")
                + ", but no previously-evicted evidence covers the partial "
                "categor"
                + ("y" if len(partial_categories) == 1 else "ies")
                + "; the critic cannot alter Project Truth or invent new "
                "retrieval on its own authority, so it raises a Context "
                "Finding for human/other-system review instead."
            ),
            cost_tokens_estimate=CRITIC_BASE_COST_TOKENS,
        )
    additional_tokens = sum(fused.item.token_estimate for fused in candidates)
    cost_estimate = CRITIC_BASE_COST_TOKENS + additional_tokens
    if assembled.total_tokens + additional_tokens > budget_tokens:
        return CriticOutcome(
            action="raised_finding",
            reassembled=None,
            outcome_summary=(
                f"Found {len(candidates)} evicted item(s) covering "
                f"{', '.join(partial_categories)}, but recovering them would "
                "exceed the context budget; the critic cannot widen a "
                "worker's budget on its own authority, so it raises a "
                "Context Finding for human/other-system review instead."
            ),
            cost_tokens_estimate=cost_estimate,
        )
    candidate_set = set(candidates)
    reassembled = AssembledContext(
        included=tuple(assembled.included) + tuple(candidates),
        evicted=tuple(
            fused for fused in assembled.evicted if fused not in candidate_set
        ),
        total_tokens=assembled.total_tokens + additional_tokens,
    )
    return CriticOutcome(
        action="requested_additional_retrieval",
        reassembled=reassembled,
        outcome_summary=(
            f"Recovered {len(candidates)} previously-evicted item(s) covering "
            f"{', '.join(partial_categories)} from evidence the Chapter 5.2 "
            "retrievers already fused this compile() call; no new retriever "
            "call was made (Stage 1: the critic requests from what was "
            "already retrieved, it does not run its own retrieval)."
        ),
        cost_tokens_estimate=cost_estimate,
    )
