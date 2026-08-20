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
    engine.recovery (Chapter 3.8: 'ExternalEffect | recovery | Capability adapter |
    Status only | Effect'): engine.recovery is the sole writer of this table, even
    though the actual insert/transition calls are made from the capability-adapter call
    sites that perform the real side effect (engine.workers.scripted_adapter,
    engine.workspaces.service), mirroring how engine.capabilities.broker is
    credential_handles' sole writer despite engine.workers/engine.workspaces being its
    real future callers. idempotency_key/request_hash (Chapter 12.5) are established
    through engine.events.idempotency.CommandLedger at prepare() time -- command_id is
    that ledger row's own identity, not a second, independently-invented one. status
    never regresses: PREPARED -> SENT -> CONFIRMED | FAILED | (UNKNOWN -> RECONCILING ->
    RECONCILED), enforced by engine.recovery.states.EXTERNAL_EFFECT_TRANSITIONS. Only a
    verified absence of the effect at reconciliation time permits a caller to retry the
    underlying mutation; a verified presence resolves to RECONCILED, treating the
    original attempt as the one true execution. For IRREVERSIBLE side_effect_class
    effects (Chapter 9.3), a reconciliation that cannot determine the true state raises
    rather than silently resolving. worker_run_id is a soft reference, not a foreign
    key: prepare()/mark_sent() commit in their own unit of work BEFORE the real side
    effect runs (the point of a PREPARED/SENT row surviving a crash mid-effect), while
    WorkerManagerService.invoke_run still holds the WorkerRun insert uncommitted in a
    different transaction -- the same READ COMMITTED isolation reason capability_leases
    does not FK worker_run_id (see engine.workers.service's DDE-017 module docstring).
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
