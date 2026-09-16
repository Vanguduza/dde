# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SourceAdmission(BaseModel):
    """Hash-bound admission decision for one domain-neutral source artifact revision."""

    model_config = ConfigDict(extra="forbid")

    admission_id: UUID
    source_id: UUID
    artifact_id: UUID
    tenant_id: UUID
    project_id: UUID
    content_hash: str
    compiler_version: str
    policy_version: str
    qualification_domain: str
    qualification_profile: str
    state: Literal["ADMITTED", "REJECTED", "BLOCKED", "REVOKED", "QUARANTINED"]
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
        "REFERENCE_ONLY",
        "RESTRICTED",
        "UNKNOWN",
        "REJECTED",
    ]
    analysis: dict[str, object]
    hard_failures: list[str]
    validation_obligations: list[str]
    provenance: dict[str, object]
    security_state: str
    license_state: str
    provenance_state: str
    sanitization_state: str
    injection_state: str
    revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
