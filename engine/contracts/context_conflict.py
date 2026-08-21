# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContextConflict(BaseModel):
    """
    Chapter 5.6 conflict adjudication record. Written once, alongside the ContextPackage
    it names, whenever the DCE finds two authority-rank<=6 items that contradict each
    other -- the package's status is CONFLICTED and the DCE must not merge or silently
    prefer one. `status` tracks whether the conflict has been resolved (retrieved
    resolving evidence, a raised EDR/decision task, or human escalation, per Chapter
    5.6); autonomous execution on the affected task stays blocked while `status` is
    `open`. Owned by engine.context (Chapter 3.8, alongside ContextPackage).
    """

    model_config = ConfigDict(extra="forbid")

    conflict_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    package_id: UUID
    item_a_key: str
    item_a_authority_rank: int
    item_b_key: str
    item_b_authority_rank: int
    contradiction_type: Literal[
        "overlapping_accepted_edrs",
        "superseded_item_still_authoritative",
    ]
    affected_success_criteria: list[str]
    status: Literal["open", "resolved"]
    resolution_method: (
        Literal[
            "retrieved_resolving_evidence", "decision_task_raised", "escalated_to_human"
        ]
        | None
    ) = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
