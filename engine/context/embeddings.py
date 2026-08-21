"""Versioned embedding model for the semantic index (Chapter 5.4).

The blueprint leaves the embedding model unpinned ("pgvector over chunk
embeddings", §18.7) and only mandates that its version be stored on every
vector row so a model change re-indexes instead of silently reusing stale
vectors. This module supplies a **deterministic, dependency-free feature
vector** — a hashing-trick bag-of-tokens embedding, L2-normalised — so the
index lifecycle (build, invalidation, model-version gating, semantic
retrieval) is real and testable with zero new dependencies.

**Flagged divergence (EDR).** A hashing-trick vector is a lexical feature
vector, not a transformer/semantic embedding; cosine similarity over it
surfaces lexically-overlapping code (Chapter 5.7's "semantically-similar-
but-unlinked code" tier) rather than deep semantic paraphrase. Swapping in
a real embedding model (and pgvector storage) is the intended migration:
because `EMBEDDING_MODEL_VERSION` is stored on every row and a version
bump forces a new `index_version` + re-index (see
`engine.context.index_service`), the swap is a model-version change, not a
schema change. Deferred until a model + pgvector are available (Chapter
9.6: no new dependency without a licence/maintenance decision).
"""

from __future__ import annotations

import hashlib
import math
import re

EMBEDDING_MODEL_VERSION = "dde-hash-trick-v1"
EMBEDDING_DIM = 128

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def embed(
    text: str,
    *,
    dim: int = EMBEDDING_DIM,
    model_version: str = EMBEDDING_MODEL_VERSION,
) -> list[float]:
    """Deterministic, L2-normalised feature vector for `text`.

    `model_version` is accepted and recorded so callers cannot silently
    attach an unversioned vector; the hashing trick's shape is stable for a
    given `dim`, and the version string is what `index_service` keys its
    re-index decision on.
    """
    del model_version  # shape is version-independent; the version gates re-indexing
    vector = [0.0] * dim
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Cosine similarity between two (already normalised) vectors."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    return max(0.0, min(1.0, dot))
