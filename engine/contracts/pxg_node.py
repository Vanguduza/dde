# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SourceRef(BaseModel):
    """SourceRef nested contract."""

    model_config = ConfigDict(extra="forbid")

    path: str
    symbol: str | None = None
    line: int | None = None


class PxgNode(BaseModel):
    """
    DDE-069 Project Experience Graph node -- the semantic model of what a project's
    frontend actually is, above raw DOM. Owned by engine.studio.pxg (PxgService is the
    sole writer). A node's `pxg_key` is the stable identity every other subsystem
    addresses it by: Frontend Contract obligations, canvas selection anchors, inspector
    descriptors, chat references, provenance and coverage all resolve through it, so a
    DOM reflow cannot silently repoint a selection at a different component.
    `pxg_revision` is the project-wide monotonic revision at which this node was last
    written; the project's current revision is the maximum over its nodes, and a
    mutation precondition carrying an older revision is stale rather than blindly
    applied.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: UUID
    tenant_id: UUID
    project_id: UUID
    pxg_key: str
    node_kind: Literal[
        "journey",
        "screen",
        "region",
        "component",
        "interaction",
        "state",
        "data_binding",
        "navigation",
        "responsive_state",
        "accessibility_contract",
    ]
    title: str
    parent_key: str | None = None
    pxg_revision: int
    source_refs: list[SourceRef]
    attributes: dict[str, object]
    provenance: dict[str, object]
    lock_version: int
    created_at: datetime
    updated_at: datetime
