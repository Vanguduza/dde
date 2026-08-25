"""Chapter 5.2 Documentation retriever (DDE-050).

Serves version-pinned external documentation through the docs provider as
rank-9 external evidence (Ch.5.5: external documentation is version-
pinned and never current-state). Items carry the pinned version in their
key so two versions of the same source fuse as distinct evidence rather
than silently overwriting each other.
"""

from __future__ import annotations

from pathlib import Path

from engine.capabilities.docs import DocContent, DocsProvider
from engine.capabilities.docs.provider import InProcessDocsProvider
from engine.context.model import (
    AUTHORITY_RANK_EXTERNAL_EVIDENCE,
    ContextItem,
)
from engine.contracts.task import Task

MAX_RESULT_ITEMS = 8


def _term_hits(text: str, task: Task) -> int:
    lowered = text.lower()
    terms = [
        term.lower()
        for term in " ".join([task.title, task.intent]).split()
        if len(term) >= 4
    ]
    return sum(lowered.count(term) for term in terms)


async def retrieve(
    task: Task,
    *,
    root: Path,
    expected_write_scope: tuple[str, ...],
    provider: DocsProvider | None = None,
) -> list[ContextItem]:
    active = provider or InProcessDocsProvider(root / "docs" / "external")
    if not await active.is_active():
        return []
    # `ContextItem` is frozen, so relevance ordering must be decided before
    # construction: rank_in_retriever is assigned exactly once per item,
    # from its position in the final ordering (never patched afterwards).
    candidates: list[tuple[float, str, DocContent]] = []
    for source in await active.list_sources():
        for content in await active.read(source.slug):
            hits = _term_hits(content.text, task)
            if hits <= 0:
                continue
            key = f"doc:{source.slug}@{content.version}:{content.path}"
            candidates.append((min(1.0, 0.3 + hits * 0.1), key, content))
    candidates.sort(key=lambda entry: (-entry[0], entry[1]))
    items: list[ContextItem] = []
    for rank_in_retriever, (relevance, key, content) in enumerate(
        candidates[:MAX_RESULT_ITEMS], start=1
    ):
        items.append(
            ContextItem(
                retriever="documentation",
                key=key,
                categories=("documentation",),
                authority_rank=AUTHORITY_RANK_EXTERNAL_EVIDENCE,
                rank_in_retriever=rank_in_retriever,
                relevance=relevance,
                write_scope_match=(content.path in expected_write_scope),
                content=(
                    f"[docs:{content.slug}@{content.version}] "
                    f"{content.path}\n{content.text[:2000]}"
                ),
                source_path=None,
            )
        )
    return items
