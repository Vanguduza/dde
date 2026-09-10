from __future__ import annotations

import pytest

from scripts import project_truth_local as guard


def test_exact_commit_backfill_is_accepted() -> None:
    rows: list[dict[str, object]] = [
        {
            "kind": "commit-backfill",
            "commit_sha": "abc123",
            "diff_sha256": "digest",
        }
    ]
    assert guard.recorded_in_current_ledger(
        rows=rows,
        commit="abc123",
        source_parent="parent",
        digest="digest",
        files=["path.txt"],
    )


def test_commit_backfill_digest_mismatch_is_rejected() -> None:
    rows: list[dict[str, object]] = [
        {
            "kind": "commit-backfill",
            "commit_sha": "abc123",
            "diff_sha256": "other",
        }
    ]
    assert not guard.recorded_in_current_ledger(
        rows=rows,
        commit="abc123",
        source_parent="parent",
        digest="digest",
        files=["path.txt"],
    )


def test_pure_merge_carrier_requires_parent_tree_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(guard, "commit_parents", lambda _commit: ["p1", "p2"])
    trees = {"merge": "tree-b", "p1": "tree-a", "p2": "tree-b"}
    monkeypatch.setattr(guard, "commit_tree", lambda commit: trees[commit])
    assert guard.is_pure_merge_carrier("merge")

    trees["p2"] = "tree-c"
    assert not guard.is_pure_merge_carrier("merge")
