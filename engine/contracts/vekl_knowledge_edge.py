# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLKnowledgeEdge(BaseModel):
    """
    Typed provenance-bearing rebuildable relation between declared VEKL knowledge-node
    kinds.
    """

    model_config = ConfigDict(extra="forbid")

    knowledge_edge_id: UUID
    tenant_id: UUID
    project_id: UUID
    from_node_id: UUID
    relationship: Literal[
        "derives_from",
        "governed_by",
        "observes",
        "classified_as",
        "consumes",
        "produces",
        "depends_on",
        "implemented_by",
        "verified_by",
        "realizes",
        "constrained_by",
        "supports",
        "informs",
        "verifies",
        "diagnoses",
        "conflicts_with",
        "supersedes",
        "supplies",
        "selected_by",
        "resolves",
        "binds",
        "evaluates",
        "yields",
        "proves",
        "changes",
        "invalidates",
        "derived_from",
        "challenges",
        "aggregates",
        "affects",
        "requires",
    ]
    to_node_id: UUID
    provenance_ref: str
    provenance_hash: str
    derivation_class: Literal[
        "DETERMINISTIC",
        "DECLARED",
        "VERIFIED_INFERRED",
        "RESEARCH_HYPOTHESIS",
    ]
    created_at: datetime
    updated_at: datetime
    invalidated_at: datetime | None = None
