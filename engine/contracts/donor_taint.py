# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DonorTaint(BaseModel):
    """
    Chapter 13.8 provenance taint link (DDE-047). Answers which donor evidence
    influenced a Feature DNA row, task, diff-gate report, or evidence artifact. Written
    only by DonorTaintService mutation sites; never inventable by workers.
    """

    model_config = ConfigDict(extra="forbid")

    donor_taint_id: UUID
    tenant_id: UUID
    project_id: UUID
    donor_artifact_id: UUID
    subject_kind: Literal["feature_dna", "task", "diff_gate_report", "evidence"]
    subject_id: UUID
    source_class: Literal[
        "OPEN_REUSE",
        "CONDITIONAL_REUSE",
        "SOURCE_REFERENCE_ONLY",
        "RESTRICTED",
        "UNKNOWN",
        "REJECTED",
    ]
    licence_class: str
    taint_tags: list[str]
    source_uri: str
    signed_reuse_decision_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
