"""Boundary requests and read projections for Production VEKL."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VEKLResourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_kind: str
    component_kind: str | None = None
    parent_resource_id: UUID | None = None
    source_id: UUID | None = None
    source_artifact_id: UUID | None = None
    title: str
    publisher: str
    source_uri: str | None = None
    revision: str
    content_hash: str
    source_trust: str
    reuse_class: str
    activation_modes: list[str]
    exact_versions: dict[str, str] = Field(default_factory=dict)
    license_ids: list[str] = Field(default_factory=list)
    provenance: dict[str, object] = Field(default_factory=dict)
    required_capabilities: list[str] = Field(default_factory=list)
    filesystem_scopes: list[str] = Field(default_factory=list)
    network_scopes: list[str] = Field(default_factory=list)
    secret_scopes: list[str] = Field(default_factory=list)
    sandbox_requirements: dict[str, object] = Field(default_factory=dict)
    side_effect_class: str = "PURE_READ"
    required_verifiers: list[str] = Field(default_factory=list)
    stack_constraints: dict[str, object] = Field(default_factory=dict)
    truth_constraints: dict[str, object] = Field(default_factory=dict)
    freshness: dict[str, object] = Field(default_factory=dict)
    budget: dict[str, object] = Field(default_factory=dict)
    content_excerpt: str = ""


class TaskSignatureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lifecycle_stage: str
    engineering_archetype: str | None = None
    unattended: bool = False
    constraints: dict[str, object] = Field(default_factory=dict)
    error_signatures: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    allowed_filesystem_scopes: list[str] = Field(default_factory=list)
    allowed_network_scopes: list[str] = Field(default_factory=list)
    allowed_secret_scopes: list[str] = Field(default_factory=list)
    required_verifiers: list[str] = Field(default_factory=list)
    freshness_needs: dict[str, object] = Field(default_factory=dict)
    budget: dict[str, object] = Field(default_factory=dict)


class ActivationPlanSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_mode: Literal["APPLICATION_MANUFACTURING_VEKL"]
    policy: dict[str, object]
    knowledge_context: dict[str, object] = Field(default_factory=dict)
    requested_modes: list[str]
    mandatory_resource_ids: list[UUID] = Field(default_factory=list)
    resolution_trace_id: UUID | None = None
    resolved_resource_ids: list[UUID] = Field(default_factory=list)
    available_capabilities: list[str] = Field(default_factory=list)
    available_verifiers: list[str] = Field(default_factory=list)
    sandbox_available: bool
    offline: bool = False
    task_attempt_id: UUID | None = None
    worker_run_id: UUID | None = None
    replaces_manifest_id: UUID | None = None


class ResourceOutcomeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verifier_refs: list[str]
    verified_outcome: Literal["PASS", "FAIL", "PARTIAL"]
    regressions: list[str] = Field(default_factory=list)
    iterations: int = Field(ge=0)
    rework: dict[str, object] = Field(default_factory=dict)
    cost: dict[str, object] = Field(default_factory=dict)
    latency_ms: int = Field(ge=0)
    failure_signatures: list[str] = Field(default_factory=list)
    evidence_refs: list[str]
    recorded_by: Literal["DDE_VERIFIER", "DDE_OPERATOR"] = "DDE_VERIFIER"


class ResearchFindingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_map_id: UUID
    task_refs: list[UUID]
    concern: str
    source_id: UUID | None = None
    source_artifact_id: UUID | None = None
    resource_id: UUID | None = None
    source_trust: str
    source_revision: str
    content_hash: str
    claim: str
    supporting_excerpt_hash: str
    freshness: dict[str, object] = Field(default_factory=dict)
    classification: Literal[
        "NORMAL_GUIDANCE",
        "COMPATIBILITY_SIGNAL",
        "SECURITY_SIGNAL",
        "TRUTH_CONFLICT_SIGNAL",
        "DISCOVERY_ONLY",
    ]
    confidence: str
    corroboration_refs: list[str] = Field(default_factory=list)
    project_truth_refs: list[str] = Field(default_factory=list)
    stack_refs: list[str] = Field(default_factory=list)
    impact_hypothesis: list[str] = Field(default_factory=list)


class TruthChallengeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID | None = None
    finding_ids: list[UUID]
    challenge_class: Literal[
        "SECURITY_CHALLENGE",
        "COMPATIBILITY_CHALLENGE",
        "ARCHITECTURE_CHALLENGE",
        "PRODUCT_EXPERIENCE_CHALLENGE",
        "REGULATORY_CHALLENGE",
        "PERFORMANCE_CHALLENGE",
        "OPERABILITY_CHALLENGE",
        "COST_CHALLENGE",
        "OPPORTUNITY_CHALLENGE",
    ]
    severity: Literal["INFO", "MATERIAL", "HIGH", "CRITICAL"]
    conflict: dict[str, object]
    confidence: dict[str, object]
    impact: dict[str, object]
    proposal: dict[str, object]
    decision_analysis: dict[str, object] = Field(default_factory=dict)
    reopen_conditions: list[str] = Field(default_factory=list)


class TruthChallengeReopenSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: UUID
    additional_finding_ids: list[UUID] = Field(default_factory=list)
    trigger_reason: str


class ChangeImpactSpec(BaseModel):
    """Non-authoritative observation emitted from existing change/task authority.

    This transport does not create a ChangePacket ledger. It carries the exact
    refs/hash already owned by the mutation path so VEKL can invalidate derived
    knowledge projections deterministically.
    """

    model_config = ConfigDict(extra="forbid")

    source_change_ref: str
    source_change_hash: str
    changed_contract_refs: list[str] = Field(default_factory=list)
    changed_task_refs: list[UUID] = Field(default_factory=list)
    changed_paths: list[str] = Field(default_factory=list)
    changed_schema_refs: list[str] = Field(default_factory=list)
    changed_api_refs: list[str] = Field(default_factory=list)
    changed_event_refs: list[str] = Field(default_factory=list)
    reason_code: Literal[
        "CHANGE_PACKET_CONTRACT_DELTA",
        "CONTRACT_CHANGED",
        "SCHEMA_CHANGED",
        "API_CHANGED",
        "EVENT_CHANGED",
    ] = "CHANGE_PACKET_CONTRACT_DELTA"
