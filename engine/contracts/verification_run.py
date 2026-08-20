# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CheckResult(BaseModel):
    """CheckResult nested contract."""

    model_config = ConfigDict(extra="forbid")

    check_ref: str
    kind: str
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    status: str


class ObservableOutcomeResult(BaseModel):
    """ObservableOutcomeResult nested contract."""

    model_config = ConfigDict(extra="forbid")

    outcome_id: UUID
    statement: str
    is_negative_case: bool
    check_ref: str
    status: str
    evidence_id: UUID | None = None
    evaluated_at: datetime


class VerificationRun(BaseModel):
    """
    Independent verification run over durable artifacts (Chapter 11.1). Append-only
    result: once terminal, a row is never mutated again; a re-verification creates a new
    run.
    """

    model_config = ConfigDict(extra="forbid")

    verification_run_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    task_attempt_id: UUID
    worker_run_id: UUID
    workspace_id: UUID
    oracle_id: UUID
    sequence: int
    status: str
    confidence: float
    check_results: list[CheckResult]
    outcome_results: list[ObservableOutcomeResult]
    negative_case_results: list[ObservableOutcomeResult]
    evidence_refs: list[UUID]
    started_at: datetime
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
