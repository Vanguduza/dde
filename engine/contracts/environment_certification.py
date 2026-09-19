# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EnvironmentCertification(BaseModel):
    """
    EDR-0019 Epic L machine-certifiable development-environment readiness. A capability
    is green only when it is desired, configured, live, qualified, evidenced and the
    evidence is still fresh. Self-test classes include deliberately induced failure
    (FAULT_INJECTION, EGRESS_DENIAL, SECRET_ISOLATION), because a gate whose failure
    mode has never been induced is not known to work.
    """

    model_config = ConfigDict(extra="forbid")

    certification_id: UUID
    tenant_id: UUID
    project_id: UUID
    environment: str
    environment_id: UUID | None = None
    capability_id: str
    desired: bool
    configured: bool
    live: bool
    qualified: bool
    evidenced: bool
    evidence_fresh: bool
    green: bool
    self_test_classes: list[
        Literal[
            "DETERMINISM",
            "FAULT_INJECTION",
            "RECOVERY",
            "AUTHENTICATION",
            "EGRESS_DENIAL",
            "SECRET_ISOLATION",
            "PROVIDER_FALLBACK",
            "DATABASE_MIGRATION",
            "EVIDENCE_DURABILITY",
        ]
    ]
    self_test_results: list[dict[str, object]]
    evidence_pointer: str | None = None
    certified_at: datetime | None = None
    expires_at: datetime | None = None
    certification_hash: str
    created_at: datetime
    updated_at: datetime
