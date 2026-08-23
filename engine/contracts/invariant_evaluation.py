# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Violation(BaseModel):
    """Violation nested contract."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    detail: str


class InvariantEvaluation(BaseModel):
    """
    Chapter 11.5 recorded outcome of evaluating one DomainInvariant against real rows of
    one ProductEnvironment. Append-only result: a re-evaluation creates a new row
    (idempotent replay returns the first row via the command ledger), never an
    overwrite. status=FAILED on a financial_state invariant carries the Chapter 11.5
    human-visibility marker: repair only through a named repair task, never auto-repair.
    Owned by engine.verification per Chapter 3.6's repository layout.
    """

    model_config = ConfigDict(extra="forbid")

    evaluation_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    invariant_id: UUID
    definition_version: str
    product_env_id: UUID
    datastore_ref: str | None = None
    sequence: int
    status: Literal["PASSED", "FAILED", "ERRORED"]
    violations: list[Violation]
    rows_checked: int
    financial_state: bool
    repair_task_ref: str | None = None
    seed_dataset_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
