# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DesignSourceSearchRun(BaseModel):
    """
    DDE-069 M8 durable source search request/result envelope. Provider degradation is
    preserved rather than hidden by successful results from another adapter.
    """

    model_config = ConfigDict(extra="forbid")

    search_run_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    query: str
    provider_keys: list[str]
    requested_capabilities: list[str]
    status: Literal["RUNNING", "COMPLETED", "PARTIAL", "FAILED", "BLOCKED"]
    result_count: int
    degradation: dict[str, object]
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
