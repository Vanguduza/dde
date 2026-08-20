# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Checkpoint(BaseModel):
    """
    Chapter 12.1 reconstructible continuation contract -- not a progress percentage and
    never the sole source of truth. Owned by engine.recovery (Chapter 3.6: checkpoints,
    effects, replay). tenant_id/project_id/mission_id are required by Chapter 3.2 even
    though 12.1's field sketch omits them. do_not_repeat is load-bearing: a resumed run
    must not re-execute those mutations. integrity_hash covers the reconstructible
    payload; a mismatched hash is not a valid checkpoint. Append-only: a later snapshot
    is a new row, not an update. worker_run_id is a real FK (checkpoint is recorded in
    the same unit of work as the run it snapshots, unlike ExternalEffect.prepare which
    commits before the run does). command_id is CommandLedger's identity at record()
    time (Chapter 12.5 / 12.6: every async command has a durable identity and
    idempotency key).
    """

    model_config = ConfigDict(extra="forbid")

    checkpoint_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    task_attempt_id: UUID
    worker_run_id: UUID
    context_package_id: UUID
    execution_plan_id: UUID
    completed_work: list[str]
    verified_work: list[str]
    pending_work: list[str]
    known_failures: list[str]
    next_action: str
    do_not_repeat: list[str]
    artifact_refs: list[UUID]
    lease_refs: list[UUID]
    workspace_revision: str
    integration_state: str
    event_sequence: int
    integrity_hash: str
    command_id: UUID
    created_at: datetime
    updated_at: datetime
