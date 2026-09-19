# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AutomationRunGrant(BaseModel):
    """
    A run-scoped grant. The automation runtime never holds a general DDE control token:
    a grant is bound to exactly one run, release, capability and context hash, carries
    an explicit operation/domain allowlist and action-class ceiling, and expires. It is
    single-use by default and replay of a spent or expired nonce is refused. The runtime
    cannot mint its own grant, authorize new capabilities, change task scope or mark a
    DDE task verified.
    """

    model_config = ConfigDict(extra="forbid")

    grant_id: UUID
    tenant_id: UUID
    project_id: UUID
    run_id: UUID
    release_id: UUID
    capability_id: str
    task_execution_descriptor_ref: str | None = None
    context_hash: str
    input_digest: str
    allowed_gateway_operations: list[str]
    allowed_external_domains: list[str]
    action_class_ceiling: Literal[
        "PURE_READ",
        "WORKSPACE_LOCAL",
        "EXTERNAL_IDEMPOTENT",
        "EXTERNAL_NON_IDEMPOTENT",
        "IRREVERSIBLE",
    ]
    max_uses: int
    uses_consumed: int
    nonce: str
    issued_at: datetime
    expires_at: datetime
    state: Literal["ISSUED", "CONSUMED", "EXPIRED", "REVOKED", "REPLAY_REFUSED"]
    created_at: datetime
    updated_at: datetime
