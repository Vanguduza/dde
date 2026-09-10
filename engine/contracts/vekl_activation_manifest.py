# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLActivationManifest(BaseModel):
    """
    Immutable exact-resource activation binding. Failover reuses this manifest while
    valid; invalidation is append-only in VEKLManifestInvalidation.
    """

    model_config = ConfigDict(extra="forbid")

    manifest_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    task_id: UUID
    task_attempt_id: UUID | None = None
    worker_run_id: UUID | None = None
    task_signature_id: UUID
    stack_fingerprint_id: UUID
    project_truth_hash: str
    stack_fingerprint_hash: str
    policy_hash: str
    knowledge_context: dict[str, object] | None = None
    selected_resources: list[dict[str, object]]
    tools: list[dict[str, object]]
    hooks: list[dict[str, object]]
    loops: list[dict[str, object]]
    community_evidence: list[dict[str, object]]
    freshness_state: dict[str, object]
    manifest_hash: str
    created_at: datetime
    updated_at: datetime
