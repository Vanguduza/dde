# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExperienceRecord(BaseModel):
    """
    Blueprint §6.3 authoritative DDE execution-experience record; semantic copies may be
    fed to Hermes.
    """

    model_config = ConfigDict(extra="forbid")

    experience_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    task_id: UUID | None = None
    worker_run_id: UUID | None = None
    worker_session_id: UUID | None = None
    task_signature: dict[str, object]
    worker_configuration: dict[str, object]
    outcome: dict[str, object]
    economics: dict[str, object]
    failure_signatures: list[str]
    verification_refs: list[str]
    authority_refs: list[str]
    created_at: datetime
    updated_at: datetime
