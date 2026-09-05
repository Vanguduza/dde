# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AiProviderInvocation(BaseModel):
    """
    One attributable provider/harness invocation, including fallback and usage lineage.
    """

    model_config = ConfigDict(extra="forbid")

    invocation_id: UUID
    tenant_id: UUID
    project_id: UUID
    conversation_id: UUID
    turn_id: UUID | None = None
    worker_session_id: UUID | None = None
    endpoint_id: UUID
    fallback_parent_id: UUID | None = None
    requested_profile_id: str | None = None
    requested_model_id: str | None = None
    serving_model_id: str | None = None
    reasoning_effort: Literal["FAST", "NORMAL", "DEEP", "MAXIMUM"]
    state: Literal[
        "PENDING",
        "APPROVAL_REQUIRED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "BLOCKED",
        "UNAVAILABLE",
    ]
    prompt_hash: str
    context_hash: str
    policy_hash: str
    approval_id: UUID | None = None
    worker_run_id: UUID | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_tokens: int | None = None
    reasoning_tokens: int | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    result_refs: list[str]
    error_code: str | None = None
    error_detail: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime
