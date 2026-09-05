from __future__ import annotations

from uuid import UUID

from engine.chat.context_manager import (
    DdeConversationContextManager,
    HistoryContextItem,
    estimate_tokens,
)


def _history(sequence: int, text: str) -> HistoryContextItem:
    return HistoryContextItem(
        turn_id=UUID(int=sequence),
        sequence=sequence,
        role="user" if sequence % 2 else "studio",
        intent="QUESTION",
        outcome="ANSWERED",
        text=text,
        estimated_tokens=estimate_tokens(text) + 12,
    )


def test_token_estimate_is_deterministic_and_nonzero_for_short_text() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abc") == 1
    assert estimate_tokens("abcdefgh") == 2
    assert estimate_tokens({"b": 2, "a": 1}) == estimate_tokens({"a": 1, "b": 2})


def test_compaction_summary_is_bounded_and_keeps_recent_lineage() -> None:
    items = tuple(_history(i, f"turn {i} " + "x" * 120) for i in range(1, 40))
    summary = DdeConversationContextManager._compact_history(items, max_tokens=160)
    assert estimate_tokens(summary) <= 160
    assert "Compacted earlier DDE Chat history" in summary
    assert "#39" in summary
    assert "QUESTION/ANSWERED" in summary
