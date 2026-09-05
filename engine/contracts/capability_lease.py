# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CapabilityLease(BaseModel):
    """
    Chapter 9.2's CapabilityLease -- the real authority boundary deciding whether a
    caller may invoke a capability at all (distinct from Chapter 10.3's WriteScopeLease,
    which governs which paths an already-authorized operation may touch). Owned by
    engine.capabilities (Chapter 3.8: 'Lease manager'). Scope is immutable after
    request. Worker-origin execution binds worker_run_id and must pass WorkerRun kill-
    flag enforcement; engine-owned non-worker verification subjects may leave
    worker_run_id null but must checkout an explicitly identified lease through the non-
    worker enforcement path, which refuses WorkerRun-bound leases.
    """

    model_config = ConfigDict(extra="forbid")

    lease_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    execution_plan_id: UUID
    worker_run_id: UUID | None = None
    environment_id: UUID | None = None
    capability_id: str
    capability_version: str
    resource_scope: dict[str, object]
    operation_scope: str
    constraints: dict[str, object]
    issued_by_policy_version: str
    issued_at: datetime
    expires_at: datetime
    revocable: bool
    status: str
    denied_reason: str | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    lease_hash: str
    requested_by: str
    created_at: datetime
    updated_at: datetime
