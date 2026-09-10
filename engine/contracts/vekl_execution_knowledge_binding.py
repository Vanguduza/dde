# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLExecutionKnowledgeBinding(BaseModel):
    """
    Append-only immutable execution-knowledge tuple proving the exact knowledge,
    activation and bounded context admitted at a material execution checkpoint.
    """

    model_config = ConfigDict(extra="forbid")

    execution_binding_id: UUID
    tenant_id: UUID
    project_id: UUID
    resolution_trace_id: UUID
    binding_stage: Literal["ACTIVATION_BOUND", "CONTEXT_BOUND"]
    project_truth_hash: str
    unit_lineage_id: str
    unit_revision_hash: str
    graph_revision_hash: str
    graph_neighbourhood_hash: str
    applicable_contract_fingerprints: list[str]
    technical_stack_fingerprint: str
    knowledge_route_policy_hash: str
    determinism_envelope_hash: str
    activation_manifest_id: UUID
    activation_manifest_hash: str
    context_package_id: UUID | None = None
    context_package_hash: str | None = None
    context_capsule_hashes: list[str]
    worker_delivery_hash: str
    binding_hash: str
    created_at: datetime
