# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendVerificationRequest(BaseModel):
    """
    DDE-069 durable request to re-run the existing DDE-068 acceptance bindings against
    one exact LIVE candidate preview. This record schedules and exposes verification
    work; it never manufactures a VerificationRun or verdict.
    """

    model_config = ConfigDict(extra="forbid")

    verification_request_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    candidate_id: UUID
    preview_session_id: UUID
    screen_key: str
    viewport: str
    candidate_pxg_revision: int
    source_revision: str | None = None
    content_hash: str | None = None
    task_id: UUID | None = None
    acceptance_oracle_version: str | None = None
    required_kinds: list[str]
    state: Literal["PENDING", "BLOCKED", "RUNNING", "PASSED", "FAILED", "SUPERSEDED"]
    reason: str | None = None
    verification_run_ids: list[UUID]
    lock_version: int
    created_at: datetime
    updated_at: datetime
