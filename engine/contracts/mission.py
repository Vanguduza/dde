# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Mission(BaseModel):
    """
    Manufacturing mission. Optimistic locking required by Chapter 3.5. Status values are
    those named by Chapters 4.9, 12.6 and 15.4.
    """

    model_config = ConfigDict(extra="forbid")

    mission_id: UUID
    tenant_id: UUID
    project_id: UUID
    slug: str
    title: str
    intent: str
    success_definition: str
    scope: list[str]
    requirement_refs: list[str]
    status: Literal[
        "CREATED",
        "ACTIVE",
        "PARTIAL",
        "PAUSED",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    ]
    autonomy_ceiling: int
    lock_version: int
    created_at: datetime
    updated_at: datetime
