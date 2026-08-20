# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GraphAmendment(BaseModel):
    """
    Proposed TaskGraph amendment. Workers may propose; only the Task Planner mutates the
    graph.
    """

    model_config = ConfigDict(extra="forbid")

    amendment_id: UUID
    graph_id: UUID
    proposed_by: str
    amendment_type: Literal[
        "add_task",
        "split_task",
        "add_edge",
        "retire_task",
        "widen_scope",
    ]
    justification: str
    evidence_refs: list[str]
    affected_task_ids: list[UUID]
    requested_write_scope: list[str]
