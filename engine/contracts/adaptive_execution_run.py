# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AdaptiveExecutionRun(BaseModel):
    """
    EDR-0019 Amendment 1. Durable state for one adaptive execution attempt against a
    placement decision. Fallback may occur only at a declared checkpoint and never mid-
    effect, so a run carries the work/diff/context hashes it hands to its successor and
    points back at the run it replaced. Until DDE-076/077 land TaskExecutionDescriptor
    and ExecutionStrategy this references a descriptor by an untyped ref; it does not
    itself become an execution authority, and the existing routing authority still
    chooses placement.
    """

    model_config = ConfigDict(extra="forbid")

    adaptive_run_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    task_id: UUID | None = None
    placement_id: UUID
    task_execution_descriptor_ref: str | None = None
    attempt: int
    state: Literal[
        "PREPARED",
        "RUNNING",
        "CHECKPOINT_REACHED",
        "FALLBACK_PENDING",
        "FALLBACK_APPLIED",
        "COMPLETED",
        "FAILED",
        "ABANDONED",
    ]
    checkpoint_kind: (
        Literal[
            "TASK_START", "VERIFIER_BOUNDARY", "CHECKPOINT_COMMIT", "EFFECT_BOUNDARY"
        ]
        | None
    ) = None
    carried_work_state_hash: str | None = None
    carried_diff_hash: str | None = None
    carried_context_hash: str | None = None
    completed_verifier_refs: list[str]
    previous_adaptive_run_id: UUID | None = None
    fallback_reason: str | None = None
    provider_lease_id: UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
