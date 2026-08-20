# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IntegrationProposal(BaseModel):
    """
    Chapter 10.4's merge queue entry: one real task branch rebased, gated and (if it
    clears every gate) fast-forwarded onto its mission integration branch. Owned by
    engine.integration.
    """

    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    task_attempt_id: UUID
    source_branch: str
    base_revision: str
    proposed_revision: str
    diff_summary: str
    changed_paths: list[str]
    scope_lease_id: UUID
    pre_integration_verification_ref: UUID
    status: str
    conflict_class: str | None = None
    attempts: int
    created_at: datetime
    updated_at: datetime
