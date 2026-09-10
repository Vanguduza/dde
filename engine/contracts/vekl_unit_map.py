# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLUnitMap(BaseModel):
    """
    Rebuildable knowledge projection over one dependency-coherent TaskGraph region;
    never Task authority.
    """

    model_config = ConfigDict(extra="forbid")

    unit_map_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_graph_id: UUID
    task_graph_version: int
    task_ids: list[UUID]
    unit_lineage_id: str
    unit_revision_hash: str
    unit_boundary_policy_version: str
    unit_projection_compiler_version: str
    project_truth_hash: str
    applicable_truth_slice_hash: str
    stack_fingerprint_id: UUID
    stack_fingerprint_hash: str
    contract_set_hash: str
    product_experience_hash: str | None = None
    retrieval_route_policy_hash: str
    objective: str
    scope: dict[str, object]
    requirement_refs: list[str]
    edr_refs: list[str]
    constitution_refs: list[str]
    upstream_task_refs: list[UUID]
    downstream_task_refs: list[UUID]
    contracts_consumed: list[str]
    contracts_produced: list[str]
    code_targets: list[str]
    workspace_refs: list[UUID]
    product_experience_refs: list[str]
    security_refs: list[str]
    eventuality_refs: list[str]
    research_questions: list[str]
    knowledge_route_ids: list[UUID]
    required_verifiers: list[str]
    knowledge_readiness_state: Literal[
        "UNMAPPED",
        "MAPPING",
        "BLOCKED",
        "READY",
        "STALE",
        "EXEMPT_BY_POLICY",
    ]
    knowledge_exemption: dict[str, object] | None = None
    challenge_state: str
    unit_map_hash: str
    created_at: datetime
    updated_at: datetime
    invalidated_at: datetime | None = None
    invalidation_reasons: list[str]
