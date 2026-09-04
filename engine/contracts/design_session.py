# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DesignSession(BaseModel):
    """
    DDE-069 one design conversation's lifetime. Owned by engine.studio.design. A
    DesignSession is the lineage that lets `Claude /design` and Frontend Chat be the
    same control plane rather than two: the toolbar button and a chat instruction join
    the *same* session, so a user can say "take Candidate B's sidebar, keep the locked
    nav, and ask /design for three hero alternatives" without losing candidate,
    selection or source context. It records the exact design-system snapshot hash and
    PXG revision its artifacts were generated against, so an artifact produced under an
    older design system is detectably stale rather than silently applied.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    conversation_id: UUID | None = None
    candidate_id: UUID | None = None
    status: Literal["OPEN", "CLOSED", "ABANDONED"]
    scope_keys: list[str]
    design_system_hash: str
    base_pxg_revision: int
    context_manifest: dict[str, object]
    lock_version: int
    created_at: datetime
    updated_at: datetime
