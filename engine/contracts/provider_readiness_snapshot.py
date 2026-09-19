# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProviderReadinessSnapshot(BaseModel):
    """
    EDR-0019 Epic B readiness axis. Readiness is NOT capacity:
    provider_capacity_snapshots remain the observed availability/quota authority and
    this contract adds the orthogonal installed -> configured -> reachable -> qualified
    -> READY axis. READY is refused without a live probe, an attested model/harness
    identity and a fresh evidence pointer -- a configured API key is never sufficient,
    and a provider may never assert its own readiness.
    """

    model_config = ConfigDict(extra="forbid")

    readiness_snapshot_id: UUID
    tenant_id: UUID
    project_id: UUID
    provider_id: str
    harness_id: str | None = None
    endpoint_id: UUID | None = None
    environment: str
    readiness_state: Literal[
        "ABSENT",
        "INSTALLED",
        "CONFIGURED",
        "REACHABLE",
        "QUALIFIED",
        "READY",
        "DEGRADED",
        "RATE_LIMITED",
        "ACCOUNT_LIMITED",
        "AUTH_FAILED",
        "QUARANTINED",
        "REVOKED",
    ]
    capacity_snapshot_id: UUID | None = None
    model_identity_expected: str | None = None
    model_identity_attested: str | None = None
    identity_drift: bool
    qualification_evidence_pointer: str | None = None
    evidence_recorded_at: datetime | None = None
    evidence_expires_at: datetime | None = None
    evidence_fresh: bool
    probe_method: (
        Literal["LIVE_COMPLETION", "LIVE_METADATA", "HARNESS_SELFTEST", "AUTH_CHECK"]
        | None
    ) = None
    last_probe_at: datetime | None = None
    degraded_code: str | None = None
    blocking_scope: (
        Literal["NONE", "TASK", "MISSION", "PROJECT", "ENVIRONMENT"] | None
    ) = None
    owner_action_required: bool
    observed_at: datetime
    created_at: datetime
    updated_at: datetime
