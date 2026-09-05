# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScreenAuditScreenRecord(BaseModel):
    """
    One logical screen assessment within a ScreenAuditRun, anchored by stable PXG
    identity or a required contract key when implementation is missing.
    """

    model_config = ConfigDict(extra="forbid")

    record_id: UUID
    audit_run_id: UUID
    tenant_id: UUID
    project_id: UUID
    pxg_key: str
    screen_kind: str
    platform: str
    module_or_product_area: str | None = None
    route_identity: str | None = None
    source_refs: list[dict[str, object]]
    journey_refs: list[str]
    role_refs: list[str]
    feature_requirement_refs: list[str]
    data_dependency_refs: list[str]
    component_inventory_ref: str | None = None
    verification_binding_refs: list[str]
    render_evidence_refs: list[str]
    implementation_state: Literal["PRESENT", "MISSING", "ORPHANED", "UNKNOWN"]
    assessment_state: Literal[
        "PASS",
        "FAIL",
        "PARTIAL",
        "UNKNOWN",
        "BLOCKED",
        "NOT_APPLICABLE",
    ]
    dimension_states: dict[str, str]
    stale: bool
    created_at: datetime
    updated_at: datetime
