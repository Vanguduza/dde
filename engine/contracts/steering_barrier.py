# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SteeringBarrier(BaseModel):
    """
    The admission barrier a material steer places over a write-ownership scope. While a
    barrier is open no new conflicting workspace/write lease may be claimed, but
    already-active writers are allowed to run on to their own safe boundary. A barrier
    bounds new claims; it never revokes work in flight.
    """

    model_config = ConfigDict(extra="forbid")

    barrier_id: UUID
    tenant_id: UUID
    project_id: UUID
    steer_id: UUID
    mission_id: UUID
    scope_kind: Literal["MISSION", "TASK_SUBTREE", "PATH_SCOPE", "WHOLE_PROJECT"]
    write_ownership_scope: list[str]
    blocked_lease_kinds: list[Literal["WORKSPACE", "WRITE_SCOPE", "CAPABILITY"]]
    state: Literal["OPEN", "DRAINING", "SATISFIED", "RELEASED", "EXPIRED"]
    active_writer_count: int
    awaited_writer_refs: list[str]
    opened_at: datetime
    drained_at: datetime | None = None
    released_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
