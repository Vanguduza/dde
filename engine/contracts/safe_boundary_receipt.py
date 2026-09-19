# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SafeBoundaryReceipt(BaseModel):
    """
    Durable proof that one active writer reached a named safe boundary, so a steer can
    proceed and so recovery after a crash can tell whether the boundary was actually
    reached. The receipt is written before the steer is allowed to execute; a process
    crash after the receipt is recoverable, a crash before it is not treated as a
    boundary.
    """

    model_config = ConfigDict(extra="forbid")

    receipt_id: UUID
    tenant_id: UUID
    project_id: UUID
    barrier_id: UUID
    steer_id: UUID
    writer_ref: str
    worker_run_id: UUID | None = None
    task_id: UUID | None = None
    boundary_kind: Literal[
        "COMMITTED_CHECKPOINT",
        "CLEAN_STAGED_CHECKPOINT",
        "ROLLBACK_CHECKPOINT",
        "VERIFIER_COMPLETE",
        "NO_ACTIVE_WRITER",
    ]
    change_packet_ref: str | None = None
    change_packet_disposition: (
        Literal["PRESERVED", "INTEGRATED", "STAGED", "ROLLED_BACK"] | None
    ) = None
    workspace_revision: str | None = None
    evidence_pointer: str | None = None
    reached_at: datetime
    created_at: datetime
