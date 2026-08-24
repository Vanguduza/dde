# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DraftNode(BaseModel):
    """DraftNode nested contract."""

    model_config = ConfigDict(extra="forbid")

    node_key: str
    title: str
    intent: str
    task_class: Literal[
        "discovery",
        "specification",
        "decision",
        "enabling",
        "implementation",
        "integration",
        "verification",
        "repair",
        "documentation",
    ]
    parent_node_key: str | None = None
    write_scope: list[str]
    read_scope: list[str] | None = None
    success_criteria: list[str]
    estimated_effort: Literal["xs", "s", "m"] | None = None
    requirement_refs: list[str] | None = None
    feature_refs: list[str] | None = None


class DraftEdge(BaseModel):
    """DraftEdge nested contract."""

    model_config = ConfigDict(extra="forbid")

    from_node_key: str
    to_node_key: str
    edge_type: Literal[
        "depends_on",
        "produces_contract_for",
        "verifies",
        "repairs",
        "blocks_on_decision",
    ]
    contract_ref: str | None = None


class Refusal(BaseModel):
    """Refusal nested contract."""

    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    node_keys: list[str] | None = None


class PlanDraft(BaseModel):
    """
    Chapter 4.3 model-assisted planning: one model-proposed task-graph draft, recorded
    as untrusted input. A draft is never an executable graph -- it becomes usable only
    through the deterministic TaskPlanner/TaskGraphService validation gate (DRAFT ->
    VALIDATING -> APPROVED|REJECTED), and a model can never emit an executable graph
    directly. origin records provenance (which planner proposed the nodes); adapter_ref
    names the capability-contract surface behind which any live model call lives; no
    vendor SDK is imported by engine code. status records the durable promotion
    lifecycle: PROPOSED -> VALIDATED | REJECTED at this table, then PROMOTED once a
    validated draft's nodes land as a real TaskGraph version.
    """

    model_config = ConfigDict(extra="forbid")

    draft_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    origin: Literal["model_assisted", "human_authored"]
    adapter_ref: str | None = None
    origin_policy_version: str
    nodes: list[DraftNode]
    edges: list[DraftEdge]
    status: Literal["PROPOSED", "VALIDATED", "REJECTED", "PROMOTED"]
    refusals: list[Refusal]
    promoted_graph_id: UUID | None = None
    provenance_key: str
    created_by_principal: UUID
    created_at: datetime
    updated_at: datetime
