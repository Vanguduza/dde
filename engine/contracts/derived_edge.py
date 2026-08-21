# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DerivedEdge(BaseModel):
    """
    Chapter 5.10 knowledge-graph derived edge: recomputed per integrated commit,
    disposable, never versioned (symbol->symbol, test->symbol, file->module,
    requirement->symbol inferred). Advisory only -- never sole proof of traceability.
    Every row carries `derived_at`, `derived_from_commit` and `deriver_version` so graph
    staleness (share of derived edges older than the head commit) is a computable,
    monitored metric. A recompute for a commit replaces the prior generation for the
    same project rather than accumulating rows across commits. Owned by engine.knowledge
    (Chapter 3.8, alongside the rest of the knowledge graph).
    """

    model_config = ConfigDict(extra="forbid")

    derived_edge_id: UUID
    tenant_id: UUID
    project_id: UUID
    edge_type: Literal[
        "symbol_to_symbol",
        "test_to_symbol",
        "file_to_module",
        "requirement_to_symbol_inferred",
    ]
    source_key: str
    target_key: str
    derived_at: datetime
    derived_from_commit: str
    deriver_version: str
    created_at: datetime
    updated_at: datetime
