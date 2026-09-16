# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SourceRecord(BaseModel):
    """
    Domain-neutral project-scoped Source Intelligence authority. Configuration is
    metadata only and MUST NOT contain credentials.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    tenant_id: UUID
    project_id: UUID
    provider_key: str
    display_name: str
    source_domain: Literal[
        "DESIGN",
        "AUTOMATION",
        "CODE",
        "DOCUMENTATION",
        "REPOSITORY",
        "PACKAGE",
        "OTHER",
    ]
    source_class: str
    source_kind: str
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
    status: Literal["AVAILABLE", "DEGRADED", "BLOCKED", "DISABLED", "REVOKED"]
    policy_revision: str
    config: dict[str, object]
    revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
