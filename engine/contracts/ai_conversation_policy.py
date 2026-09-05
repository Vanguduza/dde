# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AiConversationPolicy(BaseModel):
    """
    DDE-owned reusable conversation reasoning/permission/tool/fallback/budget policy.
    """

    model_config = ConfigDict(extra="forbid")

    policy_id: UUID
    tenant_id: UUID
    project_id: UUID
    name: str
    reasoning_effort: Literal["FAST", "NORMAL", "DEEP", "MAXIMUM"]
    permission_profile: Literal[
        "READ_ONLY",
        "WORKSPACE_EDIT",
        "AUTONOMOUS_LOCAL",
        "APPROVAL_GATED",
    ]
    toolset_ids: list[str]
    allowed_capability_ids: list[str]
    denied_capability_ids: list[str]
    fallback_chain: list[dict[str, object]]
    max_turns: int | None = None
    context_token_budget: int
    cost_budget_usd: float | None = None
    quality_priority: int
    latency_priority: int
    independent_review_required: bool
    created_by: UUID | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
