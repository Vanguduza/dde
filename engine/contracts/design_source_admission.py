# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DesignSourceAdmission(BaseModel):
    """
    DDE-069 M8 Design System Compiler/admission result pinned to exact source content.
    Hard failures block candidate use and cannot be averaged away by scores.
    """

    model_config = ConfigDict(extra="forbid")

    admission_id: UUID
    artifact_id: UUID
    tenant_id: UUID
    project_id: UUID
    content_hash: str
    compiler_version: str
    framework_state: Literal["PASS", "FAIL", "UNKNOWN"]
    license_state: Literal["PASS", "FAIL", "CONDITIONAL", "UNKNOWN"]
    dependency_state: Literal["PASS", "FAIL", "UNKNOWN"]
    security_state: Literal["PASS", "FAIL", "UNKNOWN"]
    accessibility_state: Literal["PASS", "FAIL", "PARTIAL", "UNKNOWN"]
    design_system_state: Literal["PASS", "FAIL", "PARTIAL", "UNKNOWN"]
    token_mapping_report: dict[str, object]
    unsupported_behaviors: list[str]
    hard_failures: list[str]
    validation_obligations: list[str]
    state: Literal["ADMITTED", "REJECTED", "BLOCKED"]
    created_at: datetime
    updated_at: datetime
