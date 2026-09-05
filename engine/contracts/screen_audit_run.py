# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScreenAuditRun(BaseModel):
    """
    DDE-069 reproducible Screen Audit execution pinned to exact PXG/Frontend Contract
    inputs. Owned by engine.studio.audit; summary_state never turns unknown evidence
    into a pass.
    """

    model_config = ConfigDict(extra="forbid")

    audit_run_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    source_revision: str | None = None
    pxg_revision: int
    frontend_contract_id: UUID | None = None
    frontend_contract_version: int | None = None
    policy_version: str
    role_policy_hash: str | None = None
    design_system_hash: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    status: Literal[
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "BLOCKED",
        "SUPERSEDED",
    ]
    trigger: Literal[
        "FULL",
        "INCREMENTAL",
        "MANUAL",
        "CONTRACT_CHANGE",
        "PXG_CHANGE",
        "PROMOTION",
        "VERIFICATION_CHANGE",
        "SOURCE_CHANGE",
    ]
    parent_audit_run_id: UUID | None = None
    summary_state: Literal[
        "PASS",
        "FAIL",
        "PARTIAL",
        "UNKNOWN",
        "BLOCKED",
        "NOT_APPLICABLE",
    ]
    affected_keys: list[str]
    stale: bool
    lock_version: int
    created_at: datetime
    updated_at: datetime
