# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResearchCursor(BaseModel):
    """
    EDR-0019 Epic E durable observation cursor. Progress is only understandable as a
    delta, so the Research Observatory answers 'what changed since the last cursor' from
    these revisions rather than recomputing totals. The cursor is also the idempotent
    restart point after process failure.
    """

    model_config = ConfigDict(extra="forbid")

    cursor_id: UUID
    tenant_id: UUID
    project_id: UUID
    research_mission_id: UUID
    coverage_revision: int
    packet_revision: int
    admission_revision: int
    graph_revision: int
    last_event_sequence: int
    last_cell_id: UUID | None = None
    last_packet_id: UUID | None = None
    last_provider_run_id: UUID | None = None
    observed_at: datetime
    created_at: datetime
    updated_at: datetime
