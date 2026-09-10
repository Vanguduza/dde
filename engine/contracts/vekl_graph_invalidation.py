# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLGraphInvalidation(BaseModel):
    """
    Append-only invalidation event for stale knowledge projections, traces or manifests.
    """

    model_config = ConfigDict(extra="forbid")

    graph_invalidation_id: UUID
    tenant_id: UUID
    project_id: UUID
    unit_map_id: UUID | None = None
    manifest_id: UUID | None = None
    resolution_trace_id: UUID | None = None
    reason_code: Literal[
        "VEKL_PROJECT_TRUTH_CHANGED",
        "VEKL_UNIT_MAP_CHANGED",
        "VEKL_GRAPH_NEIGHBOURHOOD_CHANGED",
        "VEKL_CONTRACT_CHANGED",
        "VEKL_STACK_FINGERPRINT_CHANGED",
        "VEKL_TASK_SIGNATURE_CHANGED",
        "VEKL_SOURCE_ADMISSION_REVOKED",
        "VEKL_RESOURCE_REVOKED",
        "VEKL_SECURITY_EVIDENCE_STALE",
        "VEKL_PRODUCT_EXPERIENCE_CHANGED",
        "VEKL_CHALLENGE_ACCEPTED",
        "VEKL_RESOLUTION_ENVELOPE_CHANGED",
    ]
    detail: dict[str, object]
    observed_truth_hash: str
    previous_hash: str | None = None
    observed_hash: str | None = None
    created_at: datetime
    updated_at: datetime
