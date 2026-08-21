"""Internal value objects for the Chapter 5.10 knowledge graph (DDE-033).

None of these are wire contracts -- `schemas/objects/asserted_edge.json`
and `schemas/objects/derived_edge.json` are the durable contracts this
module owns (Chapter 3.8). These are the in-process shapes the deriver
and service pass between each other before a `DerivedEdge`/`AssertedEdge`
row is persisted.
"""

from __future__ import annotations

from dataclasses import dataclass

DERIVED_EDGE_TYPES = (
    "symbol_to_symbol",
    "test_to_symbol",
    "file_to_module",
    "requirement_to_symbol_inferred",
)
ASSERTED_EDGE_TYPES = (
    "requirement_to_feature",
    "requirement_to_edr",
    "task_to_requirement",
    "evidence_to_requirement",
    "decision_to_consequence",
)


@dataclass(frozen=True)
class DerivedEdgeCandidate:
    """One derived edge the Chapter 5.2-style structural deriver computed
    for the current commit, before it is stamped with `derived_at` and
    persisted as a `DerivedEdge` row."""

    edge_type: str
    source_key: str
    target_key: str


@dataclass(frozen=True)
class GraphStaleness:
    """Chapter 5.10: "Graph staleness (share of derived edges older than
    the head commit) is a monitored metric." `stale_count` is the number
    of persisted `DerivedEdge` rows whose `derived_from_commit` does not
    match `head_commit`; `total_count` is zero only when no derived edges
    exist for the project yet, in which case staleness is reported as
    `0.0` (vacuously fresh) rather than dividing by zero."""

    head_commit: str
    total_count: int
    stale_count: int

    @property
    def stale_share(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.stale_count / self.total_count
