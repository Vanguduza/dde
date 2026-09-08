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
    requested_modes: list[str]
    mandatory_resource_ids: list[UUID] = Field(default_factory=list)
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
