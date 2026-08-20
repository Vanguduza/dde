"""Chapter 5.3 fusion: reciprocal rank fusion across the Stage 1
retrievers, then multiplicative authority/write-scope weighting.

**Flagged divergence** — the blueprint does not pin an RRF constant or a
write-scope boost factor ("Weights are a versioned `context_policy`, not
constants in code" — Chapter 5.3). No `context_policy` object exists yet
(that is later Chapter 6/13 machinery), so this module hard-codes the
smallest conventional choice: `k=60` is the constant used throughout the
original reciprocal-rank-fusion literature and most production hybrid
search systems; a write-scope boost of `1.2x` is a small, clearly-
subordinate-to-authority-rank nudge. Both should become policy fields,
not constants, whenever `context_policy` exists.

Freshness weighting (Chapter 5.3/5.5) is a constant `1.0` in Stage 1:
every retriever here only returns current-state evidence (current
Postgres rows, current working-tree files) — there is no donor/temporal/
historical retriever yet to make freshness discriminating.
"""

from __future__ import annotations

from engine.context.model import ContextItem, FusedItem

RRF_K = 60
WRITE_SCOPE_BOOST = 1.2


def authority_weight(rank: int) -> float:
    """Chapter 2.2: rank 0 has the highest precedence, so weight is
    inversely proportional to the rank number."""
    return 1.0 / rank if rank > 0 else 1.0


def fuse(retriever_results: dict[str, list[ContextItem]]) -> list[FusedItem]:
    scores: dict[str, float] = {}
    contributors: dict[str, set[str]] = {}
    best_item: dict[str, ContextItem] = {}
    for retriever_name, items in retriever_results.items():
        for item in items:
            rrf = 1.0 / (RRF_K + item.rank_in_retriever)
            weight = authority_weight(item.authority_rank)
            if item.write_scope_match:
                weight *= WRITE_SCOPE_BOOST
            scores[item.key] = scores.get(item.key, 0.0) + rrf * weight
            contributors.setdefault(item.key, set()).add(retriever_name)
            existing = best_item.get(item.key)
            if existing is None or item.authority_rank < existing.authority_rank:
                best_item[item.key] = item
    fused = [
        FusedItem(
            item=item,
            fused_score=scores[key],
            contributing_retrievers=tuple(sorted(contributors[key])),
        )
        for key, item in best_item.items()
    ]
    fused.sort(key=lambda entry: (-entry.fused_score, entry.item.key))
    return fused
