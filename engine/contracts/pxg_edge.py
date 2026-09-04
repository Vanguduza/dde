# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PxgEdge(BaseModel):
    """
    DDE-069 typed relationship between two Project Experience Graph nodes. Owned by
    engine.studio.pxg. Edges carry every relationship except containment, which is
    denormalised onto PxgNode.parent_key for tree reads. Both endpoints are pxg_keys
    rather than node UUIDs so an edge survives a node being rewritten in place, and a
    dangling edge is a reconciliation finding rather than a foreign-key crash --
    FRONTEND_STUDIO_REV3 section 30 requires PXG/source divergence to surface explicitly
    rather than let either side blindly win.
    """

    model_config = ConfigDict(extra="forbid")

    edge_id: UUID
    tenant_id: UUID
    project_id: UUID
    from_key: str
    to_key: str
    edge_kind: Literal[
        "navigates_to",
        "triggers",
        "binds_data",
        "renders_state",
        "satisfies",
        "derived_from",
        "depends_on",
        "variant_of",
    ]
    pxg_revision: int
    attributes: dict[str, object]
    created_at: datetime
    updated_at: datetime
