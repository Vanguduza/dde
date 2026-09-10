# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLResolutionTrace(BaseModel):
    """
    Immutable resolution evidence explaining exactly why one deterministic knowledge set
    was selected for one material task/unit resolution; later execution bindings are
    append-only records.
    """

    model_config = ConfigDict(extra="forbid")

    resolution_trace_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_graph_id: UUID
    task_ids: list[UUID]
    unit_map_id: UUID
    unit_lineage_id: str
    unit_revision_hash: str
    project_truth_hash: str
    applicable_truth_slice_hash: str
    stack_fingerprint_hash: str
    task_signature_hash: str
    contract_set_hash: str
    graph_snapshot_hash: str
    resolution_envelope: dict[str, object]
    traversed_node_ids: list[UUID]
    traversed_edge_ids: list[UUID]
    candidate_decisions: list[dict[str, object]]
    withheld_truth_conflicts: list[UUID]
    challenge_observation_refs: list[UUID]
    trace_hash: str
    created_at: datetime
