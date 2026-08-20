"""Chapter 5.7 budget and eviction.

Only a subset of the full ten-tier eviction order is populated in Stage
1, because only four retrievers exist: tier 0 (write scope itself) and
tier 1 (requirements/EDRs/success criteria) are never evicted; tier 3
(architecture context — folding `security_constraints` evidence in
alongside it, both being Stage 1's AGENTS.md/`docs/blueprint` lexical
hits) and tier 5 (other retrieved code, "sibling module code") are
evictable. Tiers 2, 4, 6-10 have no Stage 1 source and are simply never
populated — this is not a shortcut around the priority order, there is
nothing Stage 1 retrieves that belongs in them.

**Flagged divergence** — the blueprint does not fix a default
`context_budget`; Chapter 5.7 says it comes from "the worker profile's
capacity", which does not exist until Chapter 7/8 (execution/workers).
`DEFAULT_CONTEXT_BUDGET_TOKENS` is a conservative placeholder pending
that machinery.
"""

from __future__ import annotations

from collections import defaultdict

from engine.context.model import (
    AUTHORITY_RANK_REQUIREMENT,
    AssembledContext,
    ContextBudgetExceeded,
    ContextItem,
    FusedItem,
)
from engine.contracts.task import Task

DEFAULT_CONTEXT_BUDGET_TOKENS = 8000

TIER_WRITE_SCOPE = 0
TIER_UNEVICTABLE_AUTHORITY = 1
TIER_ARCHITECTURE_AND_SECURITY = 3
TIER_OTHER_CODE = 5
UNEVICTABLE_TIERS = frozenset({TIER_WRITE_SCOPE, TIER_UNEVICTABLE_AUTHORITY})


def _tier(item: ContextItem) -> int:
    if item.write_scope_match:
        return TIER_WRITE_SCOPE
    if item.retriever in ("authority", "task"):
        return TIER_UNEVICTABLE_AUTHORITY
    if (
        "architecture_constraints" in item.categories
        or "security_constraints" in item.categories
    ):
        return TIER_ARCHITECTURE_AND_SECURITY
    return TIER_OTHER_CODE


def _success_criteria_item(task: Task) -> FusedItem:
    content = "Success criteria:\n" + "\n".join(f"- {c}" for c in task.success_criteria)
    item = ContextItem(
        retriever="task",
        key="success_criteria",
        categories=("verification_obligations",),
        authority_rank=AUTHORITY_RANK_REQUIREMENT + 4,  # rank 7: task specification
        rank_in_retriever=1,
        relevance=1.0,
        write_scope_match=True,
        content=content,
        source_path=None,
    )
    return FusedItem(item=item, fused_score=1.0, contributing_retrievers=("task",))


def assemble(
    task: Task,
    fused_items: list[FusedItem],
    *,
    budget_tokens: int,
) -> AssembledContext | ContextBudgetExceeded:
    tiered: dict[int, list[FusedItem]] = defaultdict(list)
    tiered[TIER_UNEVICTABLE_AUTHORITY].append(_success_criteria_item(task))
    for fused in fused_items:
        tiered[_tier(fused.item)].append(fused)

    unevictable = [
        fused for tier in sorted(UNEVICTABLE_TIERS) for fused in tiered.get(tier, [])
    ]
    unevictable_tokens = sum(fused.item.token_estimate for fused in unevictable)
    if unevictable_tokens > budget_tokens:
        return ContextBudgetExceeded(
            task_id=task.task_id,
            budget_tokens=budget_tokens,
            required_tokens=unevictable_tokens,
            unevictable_tokens=unevictable_tokens,
        )

    included = list(unevictable)
    evicted: list[FusedItem] = []
    total = unevictable_tokens
    evictable_tiers = sorted(
        (tier for tier in tiered if tier not in UNEVICTABLE_TIERS), reverse=True
    )
    for tier in evictable_tiers:
        for fused in sorted(tiered[tier], key=lambda entry: -entry.fused_score):
            if total + fused.item.token_estimate <= budget_tokens:
                included.append(fused)
                total += fused.item.token_estimate
            else:
                evicted.append(fused)

    return AssembledContext(
        included=tuple(included), evicted=tuple(evicted), total_tokens=total
    )
