"""Explicit reference retriever (Chapter 5.2): "Direct fetch by ID/path",
free cost. Reads exactly the files a Task's `expected_read_scope` already
named — no search, no ranking heuristic beyond declaration order.
"""

from __future__ import annotations

from pathlib import Path

from engine.context.model import AUTHORITY_RANK_CODE, ContextItem, DiscoveryResult
from engine.context.repo import classify_categories, is_excluded, touches_scope

MAX_CONTENT_CHARS = 4000
MAX_FILES_PER_DIRECTORY = 25


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _item(
    rel_path: str, path: Path, rank: int, write_match: bool
) -> ContextItem | None:
    text = _read_text(path)
    if text is None:
        return None
    truncated = text[:MAX_CONTENT_CHARS]
    return ContextItem(
        retriever="explicit",
        key=f"file:{rel_path}",
        categories=classify_categories(rel_path, truncated),
        authority_rank=AUTHORITY_RANK_CODE,
        rank_in_retriever=rank,
        relevance=1.0,
        write_scope_match=write_match,
        content=truncated,
        source_path=rel_path,
    )


def retrieve(
    discovery: DiscoveryResult,
    *,
    root: Path,
    expected_write_scope: tuple[str, ...],
) -> list[ContextItem]:
    items: list[ContextItem] = []
    rank = 1
    for entry in discovery.resolved_paths:
        path = (root / entry).resolve()
        if path.is_file():
            item = _item(entry, path, rank, touches_scope(entry, expected_write_scope))
            if item is not None:
                items.append(item)
                rank += 1
            continue
        if not path.is_dir():
            continue
        count = 0
        for child in sorted(path.rglob("*")):
            if count >= MAX_FILES_PER_DIRECTORY:
                break
            if not child.is_file() or is_excluded(child.relative_to(root)):
                continue
            rel_child = child.relative_to(root).as_posix()
            item = _item(
                rel_child, child, rank, touches_scope(rel_child, expected_write_scope)
            )
            if item is None:
                continue
            items.append(item)
            rank += 1
            count += 1
    return items
