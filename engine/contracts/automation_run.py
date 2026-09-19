# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AutomationRun(BaseModel):
    """
    One governed automation execution. A run is successful only when the runtime reports
    completion, DDE receives the callback, the callback grant is valid, the effect
    journal is consistent and the required postcondition verifier passes. Runtime-
    reported success alone is never completion.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    task_id: UUID | None = None
    release_id: UUID
    capability_lease_id: UUID | None = None
    runtime_execution_ref: str | None = None
    state: Literal[
        "PREPARED",
        "DISPATCHED",
        "RUNNING",
        "RUNTIME_REPORTED_COMPLETE",
        "CALLBACK_RECEIVED",
        "VERIFYING",
        "VERIFIED",
        "FAILED",
        "UNVERIFIABLE",
        "UNKNOWN",
        "REVOKED",
    ]
    callback_grant_valid: bool | None = None
    effect_journal_consistent: bool | None = None
    external_effect_refs: list[str]
    verification_ref: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
