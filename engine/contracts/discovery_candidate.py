# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DiscoveryCandidate(BaseModel):
    """
    EDR-0019 Epic C open-world discovery candidate. Pre-admission identity only: a
    candidate carries no Project Truth, implementation, execution or capability
    authority and never becomes a VEKLResource by existing. lifecycle_state and
    source_trust are independent axes -- a successful sandbox trial advances
    lifecycle_state and may never raise source_trust. source_trust reuses the canonical
    vekl_resources S1..S8 vocabulary; this contract introduces no second trust
    vocabulary. candidate_id is derived deterministically from normalized_identity_key
    so independent discoveries merge evidence instead of creating duplicates.
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    tenant_id: UUID
    project_id: UUID
    canonical_locator: str
    normalized_identity_key: str
    identity_scheme: Literal[
        "GITHUB_REPOSITORY",
        "HTTP_ORIGIN_PATH",
        "PACKAGE_COORDINATE",
        "OPAQUE",
    ]
    title: str | None = None
    publisher: str | None = None
    lifecycle_state: Literal[
        "DISCOVERED",
        "TRIAGED",
        "PROVENANCE_CHECKED",
        "CONTENT_ACQUIRED",
        "SANITIZED",
        "ARCHITECTURE_CHECKED",
        "TRIAL_ELIGIBLE",
        "SANDBOX_TESTED",
        "QUALIFIED",
        "ADMITTED",
        "REJECTED",
        "SUPERSEDED",
        "REVOKED",
    ]
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
    discovered_by: Literal[
        "RESEARCH_MISSION",
        "SOURCE_INTELLIGENCE",
        "OPERATOR",
        "VEKL_GAP",
        "CORROBORATION_FOLLOW",
    ]
    discovery_refs: list[str]
    observation_count: int
    source_id: UUID | None = None
    admitted_resource_id: UUID | None = None
    supersedes_candidate_id: UUID | None = None
    license_ids: list[str]
    content_hash: str | None = None
    sanitizer_findings: list[dict[str, object]]
    architecture_findings: list[dict[str, object]]
    first_seen_at: datetime
    last_observed_at: datetime
    created_at: datetime
    updated_at: datetime
