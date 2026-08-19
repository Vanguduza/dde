# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TaskGraphEdge(BaseModel):
    """Directed TaskGraph edge."""

    model_config = ConfigDict(extra="forbid")

    edge_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    graph_id: UUID
    from_task_id: UUID
    to_task_id: UUID
    edge_type: Literal[
        "depends_on",
        "produces_contract_for",
        "verifies",
        "repairs",
        "blocks_on_decision",
    ]
    contract_ref: str | None = None
    created_at: datetime
    updated_at: datetime
