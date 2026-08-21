# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StandingApproval(BaseModel):
    """
    Chapter 13.2 bounded standing authority. A standing approval can never pre-authorise
    an IRREVERSIBLE side effect, a production change, a scope widening beyond the
    mission's declared scope, or a critical risk action. Revocation is immediate.
    task_count_used and cost_used are the durable counters authorize() increments; they
    are not a second budget, they are this row's own usage. mission_id is nullable so a
    project-level overnight window can exist without a single mission (13.2 sketch).
    Owned by engine.governance (Chapter 3.8).
    """

    model_config = ConfigDict(extra="forbid")

    standing_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    approval_types: list[str]
    blast_radius_ceiling: str
    risk_ceiling: str
    cost_ceiling: float
    task_count_ceiling: int
    path_scope: list[str]
    forbidden_operations: list[str]
    valid_from: datetime
    valid_until: datetime
    revocable_immediately: bool
    granted_by: UUID
    rationale: str
    status: str
    task_count_used: int
    cost_used: float
    revoked_at: datetime | None = None
    command_id: UUID
    created_at: datetime
    updated_at: datetime
