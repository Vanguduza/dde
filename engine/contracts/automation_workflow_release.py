# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AutomationWorkflowRelease(BaseModel):
    """
    A workflow is not executable because it exists. A release must pass validation,
    security check, sandbox certification and canary before PRODUCTION_QUALIFIED, and
    node policy is enforced at release time: arbitrary shell, unrestricted filesystem,
    unrestricted HTTP, dynamic code execution, credential enumeration, generic AI-agent
    nodes, unbounded loops and uncontrolled webhooks are prohibited or explicitly gated.
    Revocation stops future runs without deleting historical evidence.
    """

    model_config = ConfigDict(extra="forbid")

    release_id: UUID
    tenant_id: UUID
    project_id: UUID
    definition_id: UUID
    version: str
    release_hash: str
    lifecycle_state: Literal[
        "DRAFT",
        "VALIDATED",
        "SECURITY_CHECKED",
        "SANDBOX_CERTIFIED",
        "CANARY",
        "PRODUCTION_QUALIFIED",
        "REVOKED",
    ]
    node_policy_findings: list[dict[str, object]]
    prohibited_nodes_present: list[str]
    gated_nodes_present: list[str]
    allowed_external_domains: list[str]
    action_class_ceiling: Literal[
        "PURE_READ",
        "WORKSPACE_LOCAL",
        "EXTERNAL_IDEMPOTENT",
        "EXTERNAL_NON_IDEMPOTENT",
        "IRREVERSIBLE",
    ]
    security_evidence_pointer: str | None = None
    sandbox_evidence_pointer: str | None = None
    revoked_reason: str | None = None
    revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
