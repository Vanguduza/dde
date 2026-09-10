# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLKnowledgeNode(BaseModel):
    """
    Rebuildable typed graph node referencing an existing DDE authority or an explicitly
    derived projection.
    """

    model_config = ConfigDict(extra="forbid")

    knowledge_node_id: UUID
    tenant_id: UUID
    project_id: UUID
    node_kind: Literal[
        "TARGET_PROJECT",
        "PRODUCT_CONSTITUTION",
        "REQUIREMENT",
        "EDR",
        "MISSION",
        "TASK_GRAPH",
        "TASK",
        "DEVELOPMENT_UNIT_PROJECTION",
        "STACK_FINGERPRINT",
        "TASK_SIGNATURE",
        "WORKSPACE",
        "CHANGE_PACKET",
        "CONTRACT",
        "API",
        "EVENT",
        "SCHEMA",
        "CODE_MODULE",
        "PACKAGE",
        "DEPLOYMENT_TARGET",
        "PXG_NODE",
        "FRONTEND_CONTRACT_OBLIGATION",
        "SCREEN",
        "USER_JOURNEY",
        "DESIGN_AUTHORITY",
        "SECURITY_CONTROL",
        "RECOVERY_PATTERN",
        "KNOWLEDGE_CONCERN",
        "VEKL_RESOURCE",
        "SOURCE",
        "SOURCE_ARTIFACT",
        "VEKL_ACTIVATION_MANIFEST",
        "CONTEXT_PACKAGE",
        "KNOWLEDGE_RESOLUTION_TRACE",
        "ACCEPTANCE_ORACLE",
        "VERIFICATION_RUN",
        "VERIFICATION_RESULT_REF",
        "EVIDENCE",
        "RESEARCH_FINDING",
        "TRUTH_CHALLENGE",
        "APPROVAL",
    ]
    object_type: str
    object_id: UUID | None = None
    stable_ref: str
    authority_class: str
    authority_service: str
    source_revision: str | None = None
    content_hash: str
    projection_compiler_version: str
    project_truth_hash: str | None = None
    metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime
    invalidated_at: datetime | None = None
