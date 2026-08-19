# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExecutionPlan(BaseModel):
    """How a selected worker may act. Definition is hashed; status is lifecycle."""

    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    route_decision_id: UUID
    context_package_id: UUID
    worker_profile_id: str
    execution_environment_id: UUID
    workspace_policy: dict[str, object]
    capability_requirements: list[str]
    enforcement_tier: str
    autonomy_level: int
    resource_budget: dict[str, object]
    time_budget: dict[str, object]
    token_budget: dict[str, object]
    network_policy: dict[str, object]
    filesystem_policy: dict[str, object]
    verification_plan_id: UUID | None = None
    acceptance_oracle_id: UUID | None = None
    write_scope_lease_id: UUID | None = None
    checkpoint_policy: dict[str, object]
    retry_policy: dict[str, object]
    escalation_policy: dict[str, object]
    plan_hash: str
    status: str
    approved_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
