# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResearchProviderRun(BaseModel):
    """
    One provider execution for one research stage. The stage is architectural and the
    model is not: provider policy may route cheap high-throughput models to PASS_1 and
    stronger analysis models to later stages without changing the stage contract. Egress
    is recorded here -- sanitized query intent, admitted source identity and returned
    evidence hashes -- so research egress stays auditable.
    """

    model_config = ConfigDict(extra="forbid")

    provider_run_id: UUID
    tenant_id: UUID
    project_id: UUID
    research_mission_id: UUID
    cell_id: UUID | None = None
    stage: Literal[
        "PASS_1_DISCOVERY",
        "PASS_2_ANALYSIS",
        "PASS_3_DEEP_EVIDENCE",
        "PASS_4_CONTRADICTION_CHECK",
        "PASS_5_QUALIFICATION",
        "PASS_6_GRAPH_COMPILE",
        "PASS_7_CAPSULE_COMPILE",
    ]
    provider_id: str
    model_identity_requested: str | None = None
    model_identity_attested: str | None = None
    request_class: Literal["PUBLIC", "PROJECT_LOCAL"]
    sanitized_query_hash: str
    egress_recorded: bool
    returned_evidence_hashes: list[str]
    admitted_source_refs: list[str]
    outcome: Literal[
        "PENDING",
        "SUCCEEDED",
        "MALFORMED",
        "REFUSED",
        "RATE_LIMITED",
        "FAILED",
        "TIMEOUT",
    ]
    error_class: str | None = None
    cost: dict[str, object]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
