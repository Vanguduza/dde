# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AutomationPatternDescriptor(BaseModel):
    """
    Sanitized immutable workflow-automation engineering pattern derived from quarantined
    raw workflows.
    """

    model_config = ConfigDict(extra="forbid")

    descriptor_id: UUID
    tenant_id: UUID
    project_id: UUID
    snapshot_id: UUID
    artifact_id: UUID
    pattern_lineage_id: str
    pattern_revision_hash: str
    archetype: str
    guidance_polarity: Literal["POSITIVE", "ANTI_PATTERN", "OBSERVATION_ONLY"]
    title: str
    summary: str
    trigger_classes: list[str]
    action_classes: list[str]
    integration_classes: list[str]
    control_flow: dict[str, object]
    resilience_controls: list[str]
    security_controls: list[str]
    observability_controls: list[str]
    failure_modes: list[str]
    required_capabilities: list[str]
    stack_constraints: dict[str, object]
    source_workflow_refs: list[str]
    source_workflow_hashes: list[str]
    parser_version: str
    sanitizer_version: str
    scanner_version: str
    descriptor_hash: str
    topology_hash: str
    topology_compiler_version: str
    security_findings: list[str]
    pii_findings: list[str]
    secret_findings: list[str]
    prompt_findings: list[str]
    implementation_guidance: list[str]
    anti_pattern_notes: list[str]
    auth_pattern: dict[str, object]
    retry_error_pattern: dict[str, object]
    idempotency_pattern: dict[str, object]
    persistence_pattern: dict[str, object]
    worker_safe_capsule: dict[str, object]
    created_at: datetime
    updated_at: datetime
