# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TaskGraph(BaseModel):
    """
    Versioned task graph. Nodes and edges are stored in tasks and task_graph_edges.
    """

    model_config = ConfigDict(extra="forbid")

    graph_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    version: int
    supersedes_id: UUID | None = None
    status: str
    planning_mode: Literal["template", "model_assisted", "human_authored"]
    planner_policy_version: str
    rationale: str
    open_questions: list[str]
    graph_hash: str
    created_by_principal: UUID
    lock_version: int
    created_at: datetime
    updated_at: datetime
