# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendChatChangeReview(BaseModel):
    """
    DDE-069 durable review decision over one workspace path at one diff hash. ACCEPTED
    is review state only; it does not commit or promote code.
    """

    model_config = ConfigDict(extra="forbid")

    review_id: UUID
    tenant_id: UUID
    project_id: UUID
    conversation_id: UUID
    workspace_id: UUID
    path: str
    base_revision: str | None = None
    workspace_revision: str | None = None
    diff_hash: str
    decision: Literal["PENDING", "ACCEPTED", "REVERTED"]
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
