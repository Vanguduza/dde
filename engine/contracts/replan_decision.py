# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReplanDecision(BaseModel):
    """Per-node dispositions produced by TaskPlanner.replan (Chapter 4.6)."""

    model_config = ConfigDict(extra="forbid")

    graph_id: UUID
    trigger: str
    dispositions: dict[
        str, Literal["PRESERVE", "QUIESCE", "SUPERSEDE", "RETIRE", "REVERT"]
    ]
