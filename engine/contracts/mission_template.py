# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TemplateNode(BaseModel):
    """TemplateNode nested contract."""

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
    estimated_effort: Literal["xs", "s", "m"]
    blast_radius: Literal["local", "module", "cross_module", "system"] | None = None
    risk_class: Literal["low", "medium", "high", "critical"] | None = None


class TemplateEdge(BaseModel):
    """TemplateEdge nested contract."""

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


class MissionTemplate(BaseModel):
    """
    Chapter 4.3 mission template: a first-class registry object with its own version and
    conformance tests, by which planning gets cheaper and more predictable over time.
    The definition is immutable (Chapter 3.10): a material change registers a new
    template_version content-hashed over the template fields, never an overwrite. status
    is the registry lifecycle (ACTIVE -> RETIRED); RETIRED is terminal because un-
    retiring would silently re-attach old decomposition semantics under a name consumers
    already stopped trusting -- re-declare a fresh version instead.
    planner_policy_version records which deterministic planner policy produced graphs
    instantiated from this template.
    """

    model_config = ConfigDict(extra="forbid")

    template_id: UUID
    tenant_id: UUID
    project_id: UUID
    template_key: str
    template_version: str
    description: str
    nodes: list[TemplateNode]
    edges: list[TemplateEdge]
    status: Literal["ACTIVE", "RETIRED"]
    planner_policy_version: str
    created_by: str
    created_at: datetime
    updated_at: datetime
