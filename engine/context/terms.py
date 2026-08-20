"""Shared search-term extraction for the lexical and structural
retrievers (Chapter 5.2). Deliberately simple stdlib tokenisation — no
NLP dependency (Chapter 9.6: stdlib is sufficient for keyword matching)."""

from __future__ import annotations

import re

from engine.contracts.task import Task

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "have",
        "has",
        "are",
        "was",
        "were",
        "will",
        "must",
        "should",
        "when",
        "then",
        "than",
        "task",
        "each",
        "per",
        "not",
        "all",
        "any",
    }
)
MAX_TERMS = 8
MIN_TERM_LENGTH = 3


def extract_terms(task: Task) -> tuple[str, ...]:
    """Case-insensitive, order-preserving, deduplicated term list drawn
    from the parts of a Task a human would search on: title, intent and
    success criteria — not the whole object graph."""
    text = " ".join([task.title, task.intent, *task.success_criteria])
    seen: dict[str, None] = {}
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0).lower()
        if len(token) < MIN_TERM_LENGTH or token in _STOPWORDS or token.isdigit():
            continue
        seen.setdefault(token, None)
        if len(seen) >= MAX_TERMS:
            break
    return tuple(seen.keys())
