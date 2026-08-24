# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CapturedProviderCredential(BaseModel):
    """
    Chapter 14.3 static-secret capture metadata -- durable, non-secret record of an
    operator-pasted provider credential (e.g. OpenSandbox API key) admitted through the
    Credential Broker seam. Owned by engine.capabilities.broker. This row NEVER carries
    the raw secret: only secret_hash (SHA-256), last4, and fingerprint for audit/UI
    confirmation. Raw material lives exclusively in the broker-private static vault
    table (not this contract). A material re-capture supersedes the prior CAPTURED row
    (status SUPERSEDED) rather than mutating it.
    """

    model_config = ConfigDict(extra="forbid")

    capture_id: UUID
    tenant_id: UUID
    project_id: UUID
    provider_id: str
    domain: str | None = None
    secret_hash: str
    fingerprint: str
    last4: str
    status: Literal["CAPTURED", "REVOKED", "SUPERSEDED"]
    supersedes_capture_id: UUID | None = None
    superseded_by_capture_id: UUID | None = None
    captured_by: str
    captured_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
