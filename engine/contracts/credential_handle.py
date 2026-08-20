# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CredentialHandle(BaseModel):
    """
    Chapter 14.3's Credential Broker output -- the real record of a short-lived
    credential or scoped execution handle issued in exchange for a valid, currently-
    ACTIVE CapabilityLease. Owned by engine.capabilities.broker (Chapter 3.8:
    'Credential handle | capabilities/broker | Credential Broker | Status only |
    Broker'). This row never carries the raw secret value: `secret_hash` is a SHA-256
    digest only (Chapter 14.3: 'Audit records store metadata and hashes, never secret
    material'); the actual short-lived value is returned to the issuing caller exactly
    once, in process, and is never persisted anywhere. `renew()` never mutates an
    existing row's scope fields -- it mints a new handle referencing
    `supersedes_handle_id`, mirroring CapabilityDescriptor's own supersession pattern
    (Chapter 3.10: 'a material change creates a new version ... it never overwrites').
    """

    model_config = ConfigDict(extra="forbid")

    handle_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    worker_run_id: UUID | None = None
    lease_id: UUID
    capability_id: str
    provider_id: str
    provider_ref: str | None = None
    resource_scope: dict[str, object]
    issued_by_policy_version: str
    secret_hash: str
    status: Literal["ISSUED", "EXPIRED", "REVOKED", "SUPERSEDED"]
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    supersedes_handle_id: UUID | None = None
    superseded_by_handle_id: UUID | None = None
    requested_by: str
    created_at: datetime
    updated_at: datetime
