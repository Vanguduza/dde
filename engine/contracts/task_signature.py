# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TaskSignature(BaseModel):
    """
    Deterministic VEKL extension of an existing Task identity and its execution
    constraints.
    """

    model_config = ConfigDict(extra="forbid")

    signature_id: UUID
    tenant_id: UUID
    project_id: UUID
    task_id: UUID
    fingerprint_id: UUID
    lifecycle_stage: str
    task_class: str
    constraints: dict[str, object]
    risk_category: str
    error_signatures: list[str] | None = None
    required_capabilities: list[str]
    allowed_filesystem_scopes: list[str] | None = None
    allowed_network_scopes: list[str] | None = None
    allowed_secret_scopes: list[str] | None = None
    required_verifiers: list[str]
    freshness_needs: dict[str, object]
    budget: dict[str, object]
    signature_hash: str
    created_at: datetime
    updated_at: datetime
