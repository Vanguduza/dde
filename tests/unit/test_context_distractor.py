"""Distractor-pressure metric for the Context Critic (comparable-systems
adoption #9) -- pure computation tests.

Every fixture here exercises the real TF-IDF/cosine pipeline in
`engine.context.similarity` through `evaluate_distractor_pressure`; no
mock stands in for the similarity math.
"""

from __future__ import annotations

from engine.context.critic import (
    DISTRACTOR_AUTHORITY_RANK_FLOOR,
    DISTRACTOR_PRESSURE_FINDING_KIND,
    evaluate_distractor_pressure,
)
from engine.context.model import AssembledContext, ContextItem, FusedItem
from engine.context.similarity import (
    DISTRACTOR_SIMILARITY_THRESHOLD,
    cosine_similarity,
    pairwise_similarities,
    tfidf_vector,
    tokenize,
)


def _item(key: str, content: str, authority_rank: int = 8) -> FusedItem:
    return FusedItem(
        item=ContextItem(
            retriever="lexical",
            key=key,
            categories=("impacted_code_and_deps",),
            authority_rank=authority_rank,
            rank_in_retriever=1,
            relevance=1.0,
            write_scope_match=False,
            content=content,
            source_path=None,
        ),
        fused_score=1.0,
        contributing_retrievers=("lexical",),
    )


def _assembled(*items: FusedItem) -> AssembledContext:
    return AssembledContext(
        included=tuple(items),
        evicted=(),
        total_tokens=sum(item.item.token_estimate for item in items),
    )


NEAR_DUP_A = (
    "retry policy: the worker retries the failed request three times "
    "with exponential backoff before escalating to the human queue and "
    "records every retry attempt on the durable worker run row for "
    "attribution and later recovery replays"
)
NEAR_DUP_B = (
    "retry policy: the worker retries a failed request three times with "
    "exponential backoff, escalating to the human queue, and records every "
    "retry attempt on the durable worker run row for attribution and later "
    "recovery replays"
)
UNRELATED = (
    "workspace provisioning allocates one detached git worktree per task "
    "attempt and records its revision on every checkpoint row"
)


def test_identical_content_scores_exactly_one() -> None:
    tokens = tokenize(NEAR_DUP_A)
    idf = {term: 1.0 for term in tokens}
    vector = tfidf_vector(tokens, idf)
    assert cosine_similarity(vector, vector) == 1.0


def test_disjoint_content_scores_zero() -> None:
    left = tfidf_vector(tokenize(NEAR_DUP_A), {})
    right = tfidf_vector(tokenize(UNRELATED), {})
    assert cosine_similarity(left, right) == 0.0


def test_paraphrase_pair_crosses_threshold_and_unrelated_does_not() -> None:
    pairs = pairwise_similarities([NEAR_DUP_A, NEAR_DUP_B, UNRELATED])
    flagged = {(pair.index_a, pair.index_b) for pair in pairs}
    assert (0, 1) in flagged
    assert (0, 2) not in flagged
    assert (1, 2) not in flagged


def test_clean_assembly_produces_no_finding() -> None:
    assembled = _assembled(
        _item("file:a.py", NEAR_DUP_A),
        _item("file:c.md", UNRELATED),
    )
    result = evaluate_distractor_pressure(assembled)
    assert result.clusters == ()
    assert result.finding is None


def test_low_authority_near_duplicates_raise_distractor_finding() -> None:
    assembled = _assembled(
        _item("file:a.py", NEAR_DUP_A),
        _item("file:b.py", NEAR_DUP_B),
        _item("file:c.md", UNRELATED),
    )
    result = evaluate_distractor_pressure(assembled)

    assert result.finding is not None
    assert result.finding.action == "raised_finding"
    assert len(result.clusters) == 1
    cluster = result.clusters[0]
    assert cluster.member_indices == (0, 1)
    assert cluster.max_similarity >= DISTRACTOR_SIMILARITY_THRESHOLD
    summary = result.finding.outcome_summary
    assert DISTRACTOR_PRESSURE_FINDING_KIND in summary
    # The honest disclosure must be carried on every finding.
    assert "lexical" in summary
    assert "not semantic identity" in summary


def test_high_authority_duplicates_are_not_flagged() -> None:
    """Corroborating high-authority evidence (rank <= floor: Requirements/
    EDRs surfaced twice by different retrievers) is fusion's business
    (Chapter 5.3), never distractor pressure."""
    assembled = _assembled(
        _item("requirement:REQ-1", NEAR_DUP_A, authority_rank=3),
        _item("edr:EDR-1", NEAR_DUP_B, authority_rank=4),
    )
    result = evaluate_distractor_pressure(assembled)
    assert result.clusters == ()
    assert result.finding is None


def test_cluster_below_authority_floor_is_suppressed() -> None:
    """A near-duplicate pair whose *best* member is at or above the floor
    (stronger authority than rank 7) is legitimate corroboration even when
    the other member is weak; only all-weak clusters count."""
    assembled = _assembled(
        _item("task-spec", NEAR_DUP_A, authority_rank=DISTRACTOR_AUTHORITY_RANK_FLOOR),
        _item("file:b.py", NEAR_DUP_B, authority_rank=8),
    )
    result = evaluate_distractor_pressure(assembled)
    assert result.clusters == ()
    assert result.finding is None


def test_two_disjoint_clusters_are_reported_separately() -> None:
    second_a = (
        "idempotency keys guard every external mutation against replay, so "
        "a repeated command returns the first call's stored result instead "
        "of executing the mutation twice; the ledger row records which "
        "command won and what its stored result payload was"
    )
    second_b = (
        "idempotency keys guard every external mutation against replay: a "
        "repeated command returns the first call's stored result instead of "
        "executing the mutation twice; and the ledger row records which "
        "command won and its stored result payload was"
    )
    assembled = _assembled(
        _item("file:a.py", NEAR_DUP_A),
        _item("file:b.py", NEAR_DUP_B),
        _item("file:c.py", second_a),
        _item("file:d.py", second_b),
    )
    result = evaluate_distractor_pressure(assembled)
    assert result.finding is not None
    assert len(result.clusters) == 2
    members = [cluster.member_indices for cluster in result.clusters]
    assert members == [(0, 1), (2, 3)]
