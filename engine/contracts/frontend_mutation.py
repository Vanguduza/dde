# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Preconditions(BaseModel):
    """Preconditions nested contract."""

    model_config = ConfigDict(extra="forbid")

    pxg_revision: int
    candidate_base_revision: int | None = None
    frontend_contract_version: int | None = None
    design_system_hash: str | None = None
    effective_lock_hash: str


class FrontendMutation(BaseModel):
    """
    DDE-069 one governed change to a candidate's frontend. Owned by
    engine.studio.mutations. This is the single write path: inspector edits, drag/drop,
    chat instructions, `/design` refinements, template blends, source imports, agent
    packets and keyboard operations all compile to a row of this shape, so lock,
    staleness and provenance rules cannot be bypassed by choosing a different UI
    affordance. Append-only: a reverted mutation keeps its row and gains a compensating
    one, so the edit history stays auditable rather than being rewritten.
    `preconditions` is what makes a stale edit detectable -- an apply whose recorded
    preconditions no longer hold is refused with CONFLICT_REPLAN_REQUIRED rather than
    applied against a base that moved.
    """

    model_config = ConfigDict(extra="forbid")

    mutation_id: UUID
    tenant_id: UUID
    project_id: UUID
    candidate_id: UUID
    sequence: int
    operation: Literal[
        "ADD",
        "REMOVE",
        "MOVE",
        "REORDER",
        "REPLACE",
        "RESTYLE",
        "SET_PROPERTY",
        "SET_BEHAVIOUR",
        "SET_RESPONSIVE",
    ]
    target_key: str
    origin: Literal[
        "INSPECTOR",
        "CHAT",
        "DIRECT_MANIPULATION",
        "DESIGN_PROVIDER",
        "TEMPLATE",
        "SOURCE_IMPORT",
        "AGENT",
        "KEYBOARD",
        "REPAIR",
    ]
    status: Literal["PLANNED", "APPLIED", "REVERTED", "REFUSED"]
    payload: dict[str, object]
    inverse: dict[str, object]
    preconditions: Preconditions
    refusal_code: str | None = None
    refusal_detail: str | None = None
    reverted_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
