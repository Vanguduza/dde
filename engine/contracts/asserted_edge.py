# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssertedEdge(BaseModel):
    """
    Chapter 5.10 knowledge-graph asserted edge: durable, versioned, human- or
    governance-created traceability (requirement->feature, requirement->EDR,
    task->requirement, evidence->requirement, decision->consequence). Full audit weight
    -- usable as traceability proof on its own. Never overwritten in place; `status`
    moves from `active` to `retracted` (with `retracted_at`) instead of a physical
    delete, so the assertion history stays durable. Owned by engine.knowledge (Chapter
    3.8, alongside the rest of the knowledge graph).
    """

    model_config = ConfigDict(extra="forbid")

    edge_id: UUID
    tenant_id: UUID
    project_id: UUID
    edge_type: Literal[
        "requirement_to_feature",
        "requirement_to_edr",
        "task_to_requirement",
        "evidence_to_requirement",
        "decision_to_consequence",
    ]
    source_key: str
    target_key: str
    asserted_by_principal: UUID | None = None
    asserted_by_mechanism: str
    status: Literal["active", "retracted"]
    retracted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
