# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EvidenceBinding(BaseModel):
    """EvidenceBinding nested contract."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "test",
        "db_assertion",
        "api_probe",
        "visual_diff",
        "invariant",
        "judge",
        "human",
    ]
    ref: str
    command: list[str] | None = None
    independence: str | None = None
    assertion_id: str | None = None


class ObservableOutcome(BaseModel):
    """ObservableOutcome nested contract."""

    model_config = ConfigDict(extra="forbid")

    outcome_id: UUID
    statement: str
    evidence_binding: EvidenceBinding


class AcceptanceOracle(BaseModel):
    """
    Chapter 11.2 executable acceptance definition, bound to evidence producers.
    Immutable definition; oracle_version is a content hash over definition fields only
    (Chapter 3.10). scope=task is DDE-012; scope=mission is Chapter 11.3 (DDE-037) and
    has task_id null -- a mission oracle is not a task oracle with a fabricated task_id.
    """

    model_config = ConfigDict(extra="forbid")

    oracle_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID | None = None
    oracle_version: str
    scope: Literal["task", "mission"]
    requirement_refs: list[str]
    feature_refs: list[str]
    observable_outcomes: list[ObservableOutcome]
    domain_invariants: list[str]
    negative_cases: list[ObservableOutcome]
    minimum_confidence: float
    human_assertions: list[str]
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
