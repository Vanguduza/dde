"""Chapter 5.3 reciprocal rank fusion with Chapter 2.2 authority weighting."""

from __future__ import annotations

from engine.context.fusion import RRF_K, WRITE_SCOPE_BOOST, authority_weight, fuse
from engine.context.model import ContextItem


def _item(
    retriever: str,
    key: str,
    *,
    rank: int,
    authority_rank: int,
    write_scope_match: bool = False,
) -> ContextItem:
    return ContextItem(
        retriever=retriever,
        key=key,
        categories=("impacted_code_and_deps",),
        authority_rank=authority_rank,
        rank_in_retriever=rank,
        relevance=1.0,
        write_scope_match=write_scope_match,
        content="content",
        source_path=None,
    )


def test_fuse_merges_duplicate_keys_across_retrievers() -> None:
    results = {
        "lexical": [_item("lexical", "file:a.py", rank=1, authority_rank=8)],
        "structural": [_item("structural", "file:a.py", rank=2, authority_rank=8)],
    }

    fused = fuse(results)

    assert len(fused) == 1
    assert fused[0].contributing_retrievers == ("lexical", "structural")
    expected = authority_weight(8) * (1 / (RRF_K + 1) + 1 / (RRF_K + 2))
    assert fused[0].fused_score == expected


def test_fuse_ranks_high_authority_item_above_low_authority_item_at_same_rank() -> None:
    """Chapter 2.2: a rank-3 Requirement outranks a rank-8 code item even
    at an identical raw retrieval rank, because of authority weighting."""
    results = {
        "authority": [
            _item("authority", "requirement:REQ-1", rank=1, authority_rank=3)
        ],
        "lexical": [_item("lexical", "file:a.py", rank=1, authority_rank=8)],
    }

    fused = fuse(results)

    assert [entry.item.key for entry in fused] == ["requirement:REQ-1", "file:a.py"]


def test_fuse_applies_write_scope_boost() -> None:
    results = {
        "lexical": [
            _item(
                "lexical", "file:a.py", rank=1, authority_rank=8, write_scope_match=True
            )
        ]
    }

    fused = fuse(results)

    expected = authority_weight(8) * WRITE_SCOPE_BOOST * (1 / (RRF_K + 1))
    assert fused[0].fused_score == expected


def test_fuse_is_deterministic_across_calls() -> None:
    results = {
        "lexical": [
            _item("lexical", "file:a.py", rank=1, authority_rank=8),
            _item("lexical", "file:b.py", rank=2, authority_rank=8),
        ]
    }

    first = fuse(results)
    second = fuse(results)

    assert [entry.item.key for entry in first] == [entry.item.key for entry in second]
    assert [entry.fused_score for entry in first] == [
        entry.fused_score for entry in second
    ]
