# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VEKLResource(BaseModel):
    """
    Blueprint 26A qualified engineering resource or independently qualified executable
    component. Source trust never grants reuse or execution authority.
    """

    model_config = ConfigDict(extra="forbid")

    resource_id: UUID
    tenant_id: UUID
    project_id: UUID
    parent_resource_id: UUID | None = None
    source_id: UUID | None = None
    source_artifact_id: UUID | None = None
    resource_kind: Literal[
        "SPEC",
        "OFFICIAL_DOC",
        "SKILL",
        "PLUGIN",
        "TOOL",
        "CLI",
        "MCP_SERVER",
        "LSP_SERVER",
        "REPOSITORY",
        "PACKAGE",
        "PACKAGE_METADATA",
        "RULE_PACK",
        "HOOK",
        "LOOP",
        "TEST_ORACLE",
        "SECURITY_FEED",
        "ISSUE",
        "DISCUSSION",
        "FORUM_POST",
        "COMMUNITY_SIGNAL",
        "TEMPLATE",
        "REFERENCE_ARCHITECTURE",
        "DEPLOYMENT_RECIPE",
        "OBSERVABILITY_INTEGRATION",
        "DDE_LEARNED_RECIPE",
    ]
    component_kind: str | None = None
    title: str
    publisher: str
    source_uri: str | None = None
    revision: str
    content_hash: str
    source_trust: Literal[
        "S1_NORMATIVE",
        "S2_FIRST_PARTY",
        "S3_VERIFIED_REGISTRY",
        "S4_MAINTAINED_OSS",
        "S5_MAINTAINER_COMMUNITY",
        "S6_COMMUNITY_CORROBORATED",
        "S7_DISCOVERY_ONLY",
        "S8_UNTRUSTED",
    ]
    reuse_class: Literal[
        "OPEN_REUSE",
        "CONDITIONAL_REUSE",
        "SOURCE_REFERENCE_ONLY",
        "RESTRICTED",
        "UNKNOWN",
        "REJECTED",
    ]
    lifecycle_state: Literal[
        "DISCOVERED",
        "METADATA_VERIFIED",
        "REFERENCE_QUALIFIED",
        "EXECUTION_QUARANTINED",
        "EXECUTION_EVALUATED",
        "CANARY",
        "PRODUCTION_QUALIFIED",
        "DEPRECATED",
        "REVOKED",
    ]
    activation_modes: list[
        Literal[
            "READ_ONLY_CONTEXT",
            "PROCEDURAL_GUIDANCE",
            "DISCOVERY_ONLY",
            "REFERENCE_ONLY",
            "DONOR_REUSE",
            "TOOL_EXECUTION",
            "PLUGIN_COMPONENT",
            "MCP_RUNTIME",
            "LSP_RUNTIME",
            "HOOK_ENFORCEMENT",
            "LOOP_EXECUTION",
            "TEST_ORACLE",
            "SECURITY_GATE",
            "DEPLOYMENT_ACTION",
        ]
    ]
    exact_versions: dict[str, str]
    license_ids: list[str]
    provenance: dict[str, object]
    required_capabilities: list[str]
    filesystem_scopes: list[str]
    network_scopes: list[str]
    secret_scopes: list[str]
    sandbox_requirements: dict[str, object]
    side_effect_class: Literal[
        "PURE_READ",
        "WORKSPACE_LOCAL",
        "EXTERNAL_IDEMPOTENT",
        "EXTERNAL_NON_IDEMPOTENT",
        "IRREVERSIBLE",
    ]
    required_verifiers: list[str]
    stack_constraints: dict[str, object]
    truth_constraints: dict[str, object]
    freshness: dict[str, object]
    budget: dict[str, object]
    injection_findings: list[str]
    content_excerpt: str
    created_at: datetime
    updated_at: datetime
