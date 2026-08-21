# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EvalCase(BaseModel):
    """
    Chapter 5.13's eval corpus: one frozen case sourced from a real completed mission (a
    MERGED IntegrationProposal), never synthetic. Ground truth (`required_refs`) is
    derived retrospectively and mechanically from the accepted diff's changed_paths plus
    the source Task's requirement_refs -- not guessed ahead of time. A case is `draft`
    until a human reviews and freezes it (frozen_version is set once, at freeze time,
    and the row is immutable after); it is never deleted, only `retired` with a reason.
    Owned by engine.context (Chapter 3.8, alongside the Chapter 5.4 index lifecycle it
    evaluates).
    """

    model_config = ConfigDict(extra="forbid")

    eval_case_id: UUID
    tenant_id: UUID
    project_id: UUID
    source_mission_id: UUID
    source_task_id: UUID
    source_proposal_id: UUID
    task_class: str
    is_adversarial: bool
    required_refs: list[str]
    status: Literal["draft", "frozen", "retired"]
    frozen_version: int | None = None
    retired_reason: str | None = None
    created_at: datetime
    updated_at: datetime
