# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DegradedContract(BaseModel):
    """DegradedContract nested contract."""

    model_config = ConfigDict(extra="forbid")

    broken: str
    still_works: list[str]
    will_not_do: list[str]
    restore_action: str


class CapabilityGate(BaseModel):
    """
    EDR-0019 Epic G external capability gate. Presence and configuration are not
    production readiness. READY requires complete configuration, a live probe, the
    expected identity/version, the required security policy, successful qualification
    and a still-fresh evidence pointer; evidence that ages out moves the gate to
    STALE_EVIDENCE rather than silently remaining READY. A degraded gate must state what
    is broken, what still works, what it will not do and how to restore it, so partial
    capability loss is never reported as total system failure.
    """

    model_config = ConfigDict(extra="forbid")

    gate_id: UUID
    tenant_id: UUID
    project_id: UUID
    capability_id: str
    provider_id: str | None = None
    environment: str
    desired_state: Literal[
        "UNCONFIGURED",
        "CONFIGURED",
        "REACHABLE",
        "QUALIFIED",
        "READY",
        "DEGRADED",
        "BLOCKED_EXTERNAL",
        "BLOCKED_OWNER",
        "REVOKED",
        "STALE_EVIDENCE",
    ]
    configuration_state: Literal["ABSENT", "PARTIAL", "COMPLETE"]
    reachability_state: Literal["UNKNOWN", "UNREACHABLE", "REACHABLE"]
    qualification_state: Literal["UNQUALIFIED", "IN_PROGRESS", "QUALIFIED", "FAILED"]
    readiness_state: Literal[
        "UNCONFIGURED",
        "CONFIGURED",
        "REACHABLE",
        "QUALIFIED",
        "READY",
        "DEGRADED",
        "BLOCKED_EXTERNAL",
        "BLOCKED_OWNER",
        "REVOKED",
        "STALE_EVIDENCE",
    ]
    degraded_code: str | None = None
    degraded_contract: DegradedContract | None = None
    evidence_pointer: str | None = None
    last_probe_at: datetime | None = None
    expires_at: datetime | None = None
    blocking_scope: Literal["NONE", "TASK", "MISSION", "PROJECT", "ENVIRONMENT"]
    owner_action_required: bool
    owner_action_note: str | None = None
    created_at: datetime
    updated_at: datetime
