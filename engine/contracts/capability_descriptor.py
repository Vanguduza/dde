# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CapabilityDescriptor(BaseModel):
    """
    Chapter 9.1's capability descriptor -- a declared, admitted, versioned side-
    effecting operation. Chapter 3.2 names this table's storage `capabilities` and lists
    it as one of the three named global registries, tenant-agnostic by design: it
    carries `visibility`/`owner_tenant_id` instead of a mandatory
    `tenant_id`/`project_id`. Definition fields are immutable per version (Chapter
    3.10's general principle); only `lifecycle_status`/`certification_status`/`supersede
    s_descriptor_id`/`superseded_by_descriptor_id`/`deprecated_at`/`retired_at` change
    after creation.
    """

    model_config = ConfigDict(extra="forbid")

    descriptor_id: UUID
    capability_id: str
    version: str
    category: str
    summary: str
    interface_schema_ref: str | None = None
    input_schema_ref: str | None = None
    output_schema_ref: str | None = None
    implementations: list[str]
    supported_worker_profiles: list[str]
    supported_environments: list[str]
    supported_workloads: list[str]
    risk_class: Literal["low", "medium", "high", "critical"]
    side_effect_class: Literal[
        "PURE_READ",
        "WORKSPACE_LOCAL",
        "EXTERNAL_IDEMPOTENT",
        "EXTERNAL_NON_IDEMPOTENT",
        "IRREVERSIBLE",
    ]
    enforcement_tier: Literal["T1", "T2"]
    permission_model: dict[str, object]
    cost_model: dict[str, object]
    network_requirements: dict[str, object]
    dependencies: list[str]
    provenance: dict[str, object]
    certification_status: Literal["PENDING", "CERTIFIED", "REJECTED", "STALE"]
    lifecycle_status: Literal["ACTIVE", "DEPRECATED", "RETIRED"]
    visibility: Literal["global", "tenant"]
    owner_tenant_id: UUID | None = None
    supersedes_descriptor_id: UUID | None = None
    superseded_by_descriptor_id: UUID | None = None
    descriptor_hash: str
    registered_by: str
    deprecated_at: datetime | None = None
    retired_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
