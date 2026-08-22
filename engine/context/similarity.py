"""Distractor-pressure similarity (comparable-systems adoption #9):
stdlib-only TF-IDF + cosine similarity over assembled context items.

**Honest disclosure of what this is.** TF-IDF over token sets is a
*lexical* proxy for embedding similarity, not semantic identity: two
paraphrases share no tokens and score 0.0; two boilerplate-heavy files
share many and can cross the cluster threshold without being true
distractors. The blueprint's Chapter 5.2 semantic machinery
(`engine.context.embeddings`, gated behind EDR-0002) is where a real
embedding signal would come from; this metric deliberately does not
consult it — Chapter 5.13's promotion gate has not run, so no embedding
signal may influence default behaviour (the same reason the semantic
retriever defaults off). Findings produced from this proxy are advisory
critic evidence for human review, never an authority.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_MIN_TOKEN_LENGTH = 3

#: Cosine above which two items count as near-duplicates. Chroma's sharp-
#: degradation configuration motivated the *cluster* framing; 0.85 is the
#: pairwise bar this Stage 1 slice commits to.
DISTRACTOR_SIMILARITY_THRESHOLD = 0.85


def tokenize(text: str) -> tuple[str, ...]:
    """Lowercased alphanumeric/underscore tokens, length-filtered."""
    return tuple(
        token
        for token in (match.group(0).lower() for match in _TOKEN_RE.finditer(text))
        if len(token) >= _MIN_TOKEN_LENGTH
    )


def term_frequencies(tokens: tuple[str, ...]) -> dict[str, float]:
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    total = float(len(tokens)) if tokens else 1.0
    return {term: count / total for term, count in counts.items()}


def inverse_document_frequency(documents: list[tuple[str, ...]]) -> dict[str, float]:
    """Smoothed IDF: ``ln((1 + N) / (1 + df)) + 1`` (scikit-learn's
    formulation, chosen because it never divides by zero and never yields
    a negative weight)."""
    total = len(documents)
    document_frequency: dict[str, int] = {}
    for tokens in documents:
        for term in set(tokens):
            document_frequency[term] = document_frequency.get(term, 0) + 1
    return {
        term: math.log((1 + total) / (1 + count)) + 1.0
        for term, count in document_frequency.items()
    }


def tfidf_vector(tokens: tuple[str, ...], idf: dict[str, float]) -> dict[str, float]:
    return {
        term: frequency * idf.get(term, 0.0)
        for term, frequency in term_frequencies(tokens).items()
    }


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    """Cosine between two sparse vectors; 0.0 when either is empty or the
    supports are disjoint. Floating-point noise above 1.0 is clamped so a
    vector compared with itself reports exactly 1.0."""
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    smaller, larger = (left, right) if len(left) <= len(right) else (right, left)
    dot = sum(value * larger.get(term, 0.0) for term, value in smaller.items())
    return min(1.0, dot / (left_norm * right_norm))


@dataclass(frozen=True)
class SimilarityPair:
    """One measured pairwise similarity between two item indices."""

    index_a: int
    index_b: int
    similarity: float


def pairwise_similarities(
    contents: list[str], *, threshold: float = DISTRACTOR_SIMILARITY_THRESHOLD
) -> list[SimilarityPair]:
    """TF-IDF + cosine similarity for every pair of `contents` (by index),
    returning only pairs at or above `threshold`. Deterministic order:
    ascending `(index_a, index_b)`."""
    documents = [tokenize(content) for content in contents]
    idf = inverse_document_frequency(documents)
    vectors = [tfidf_vector(tokens, idf) for tokens in documents]
    pairs: list[SimilarityPair] = []
    for index_a in range(len(vectors)):
        for index_b in range(index_a + 1, len(vectors)):
            similarity = cosine_similarity(vectors[index_a], vectors[index_b])
            if similarity >= threshold:
                pairs.append(
                    SimilarityPair(
                        index_a=index_a, index_b=index_b, similarity=similarity
                    )
                )
    return pairs


@dataclass(frozen=True)
class DistractorCluster:
    """A connected group of near-duplicate items under one low combined
    authority tier."""

    member_indices: tuple[int, ...]
    max_similarity: float
    mean_similarity: float
    worst_authority_rank: int


def build_clusters(
    *,
    contents: list[str],
    authority_ranks: list[int],
    pairs: list[SimilarityPair],
) -> list[DistractorCluster]:
    """Union-find over qualifying pairs, then keep clusters of size >= 2.

    A pair qualifies when both members sit at or below `authority_floor`
    on the caller's rank scale — high-authority duplicates (e.g. the same
    Requirement surfaced by two retrievers) are fusion's job (Chapter
    5.3), not distractor pressure. Rank semantics follow Chapter 2.2 /
    `engine.context.model`: **lower number == higher authority**, so the
    "combined tier is low" test is ``max(ranks) > authority_floor``.
    """
    parent = list(range(len(contents)))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for pair in pairs:
        root_a, root_b = find(pair.index_a), find(pair.index_b)
        if root_a != root_b:
            parent[root_b] = root_a

    members: dict[int, list[int]] = {}
    for index in range(len(contents)):
        members.setdefault(find(index), []).append(index)

    clusters: list[DistractorCluster] = []
    for indices in members.values():
        if len(indices) < 2:
            continue
        internal = [
            pair
            for pair in pairs
            if find(pair.index_a) == find(indices[0])
            and pair.index_a in indices
            and pair.index_b in indices
        ]
        similarities = [pair.similarity for pair in internal]
        clusters.append(
            DistractorCluster(
                member_indices=tuple(sorted(indices)),
                max_similarity=max(similarities),
                mean_similarity=sum(similarities) / len(similarities),
                worst_authority_rank=max(authority_ranks[index] for index in indices),
            )
        )
    clusters.sort(key=lambda cluster: cluster.member_indices)
    return clusters
