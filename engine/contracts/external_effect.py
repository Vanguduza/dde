# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExternalEffect(BaseModel):
    """
    Chapter 12.4's external effect journal -- the durable record of one real, lease-
    gated side effect a Capability adapter performs on behalf of a WorkerRun. Owned by
    engine.recovery (Chapter 3.8). engine.recovery is the sole writer; production
    mutation call sites are ScriptedWorkerAdapter (run_local_process) and
    IntegrationQueueService.submit (git update-ref). WorkspaceService.snapshot may
    journal a git read as optional extra audit, which is not the Chapter 12.4 mutation
    proof. prepare() refuses a new mutation of the same logical scope (mission +
    target_system + target_resource + operation) while SENT/UNKNOWN/RECONCILING or
    verified-present RECONCILED rows exist -- a new WorkerRun/idempotency_key does not
    bypass that recovery rule. Idempotency_key/request_hash (Chapter 12.5) are
    established through CommandLedger at prepare() time. status never regresses:
    PREPARED -> SENT -> CONFIRMED | FAILED | (UNKNOWN -> RECONCILING -> RECONCILED).
    Only a verified absence permits a new mutation attempt; verified presence sets
    confirmed_at. IRREVERSIBLE reconciliation failure raises EFFECT_IRREVERSIBLE and
    emits ExternalEffectIrreversibleEscalated. worker_run_id is a soft reference, not a
    foreign key (prepare/mark_sent commit before the side effect, while invoke_run may
    still hold the WorkerRun insert uncommitted).
    """

    model_config = ConfigDict(extra="forbid")

    effect_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    worker_run_id: UUID
    capability_lease_id: UUID
    command_id: UUID
    target_system: str
    target_resource: str
    operation: str
    side_effect_class: Literal[
        "PURE_READ",
        "WORKSPACE_LOCAL",
        "EXTERNAL_IDEMPOTENT",
        "EXTERNAL_NON_IDEMPOTENT",
        "IRREVERSIBLE",
    ]
    idempotency_key: str
    request_hash: str
    status: Literal[
        "PREPARED",
        "SENT",
        "CONFIRMED",
        "FAILED",
        "UNKNOWN",
        "RECONCILING",
        "RECONCILED",
    ]
    external_reference: str | None = None
    response_hash: str | None = None
    reconciliation_method: str | None = None
    created_at: datetime
    confirmed_at: datetime | None = None
    updated_at: datetime
