# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CapabilityGateProbe(BaseModel):
    """
    One live probe observation against a CapabilityGate. Probes are the only thing that
    may move a gate to REACHABLE or READY; a probe result is never inferred from
    configuration state.
    """

    model_config = ConfigDict(extra="forbid")

    probe_id: UUID
    tenant_id: UUID
    project_id: UUID
    gate_id: UUID
    probe_kind: Literal[
        "REACHABILITY",
        "IDENTITY",
        "VERSION",
        "AUTHENTICATION",
        "QUALIFICATION",
        "SELFTEST",
    ]
    outcome: Literal["PASSED", "FAILED", "REFUSED", "TIMEOUT", "ERROR"]
    observed_identity: str | None = None
    expected_identity: str | None = None
    latency_ms: int | None = None
    detail_hash: str | None = None
    evidence_pointer: str | None = None
    observed_at: datetime
    created_at: datetime
