# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProviderExclusion(BaseModel):
    """ProviderExclusion nested contract."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    reason: str
    readiness_state: (
        Literal[
            "ABSENT",
            "INSTALLED",
            "CONFIGURED",
            "REACHABLE",
            "QUALIFIED",
            "READY",
            "DEGRADED",
            "RATE_LIMITED",
            "ACCOUNT_LIMITED",
            "AUTH_FAILED",
            "QUARANTINED",
            "REVOKED",
        ]
        | None
    ) = None


class ExecutionPlacementDecision(BaseModel):
    """
    EDR-0019 Epic B immutable record of where a provider-routed unit of work was placed
    and why. This is evidence, not a second routing registry: selection remains owned by
    the existing routing authority and this row records the inputs, exclusions and
    fallback chain that produced the decision. Fallback may occur only at a declared
    checkpoint; a model is never switched mid-effect. Until DDE-076/077 land
    TaskExecutionDescriptor and ExecutionStrategy, task_ref/descriptor_ref are forward-
    compatible references rather than foreign keys.
    """

    model_config = ConfigDict(extra="forbid")

    placement_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    task_id: UUID | None = None
    task_execution_descriptor_ref: str | None = None
    required_capabilities: list[str]
    candidate_providers: list[str]
    excluded_providers: list[ProviderExclusion]
    selected_provider: str
    selected_harness: str | None = None
    model_identity_requested: str | None = None
    model_identity_attested: str | None = None
    capacity_snapshot_id: UUID | None = None
    readiness_snapshot_id: UUID | None = None
    fallback_chain: list[str]
    fallback_checkpoint_kind: (
        Literal[
            "TASK_START", "VERIFIER_BOUNDARY", "CHECKPOINT_COMMIT", "EFFECT_BOUNDARY"
        ]
        | None
    ) = None
    fallback_of_placement_id: UUID | None = None
    carried_work_state_hash: str | None = None
    carried_diff_hash: str | None = None
    carried_context_hash: str | None = None
    decision_hash: str
    decided_at: datetime
    created_at: datetime
    updated_at: datetime
