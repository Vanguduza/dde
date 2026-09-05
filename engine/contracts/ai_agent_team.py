# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AgentMember(BaseModel):
    """AgentMember nested contract."""

    model_config = ConfigDict(extra="forbid")

    member_id: UUID
    parent_member_id: UUID | None = None
    role: str
    task_id: UUID | None = None
    worker_session_id: UUID | None = None
    workspace_id: UUID | None = None
    model_profile_id: str | None = None
    state: Literal[
        "PENDING",
        "RUNNING",
        "PAUSED",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "BLOCKED",
    ]
    depth: int
    toolset_ids: list[str]
    budget: dict[str, object] | None = None
    result_refs: list[str]
    error_detail: str | None = None


class AiAgentTeam(BaseModel):
    """
    Bounded multi-agent team topology with explicit delegation
    depth/tool/workspace/budget lineage.
    """

    model_config = ConfigDict(extra="forbid")

    team_id: UUID
    tenant_id: UUID
    project_id: UUID
    conversation_id: UUID
    mission_id: UUID | None = None
    strategy: Literal[
        "SPECIALIST_FANOUT",
        "PARALLEL_IMPLEMENTATIONS",
        "COUNCIL",
        "REVIEW_PANEL",
        "RESEARCH_SWARM",
    ]
    state: Literal["DRAFT", "RUNNING", "PAUSED", "COMPLETED", "FAILED", "CANCELLED"]
    manager_profile_id: str | None = None
    max_depth: int
    max_children: int
    aggregate_budget: dict[str, object]
    members: list[AgentMember]
    result_refs: list[str]
    lock_version: int
    created_at: datetime
    updated_at: datetime
