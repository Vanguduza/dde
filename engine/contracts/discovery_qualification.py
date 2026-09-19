# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DiscoveryQualification(BaseModel):
    """
    EDR-0019 Epic C ResourceQualificationManifest. Qualification emits a bounded
    disposition plus an explicit authority_ceiling and allowed/forbidden uses, so useful
    material is retained at a truthful authority level instead of being discarded for
    failing the strongest admission bar. authority_ceiling reuses the canonical S1..S8
    source-trust vocabulary and can never exceed the candidate's source_trust.
    ANTI_PATTERN and FAILURE_SIGNATURE material stays retrievable but may never fill a
    positive implementation, reuse or execution slot.
    """

    model_config = ConfigDict(extra="forbid")

    qualification_id: UUID
    tenant_id: UUID
    project_id: UUID
    candidate_id: UUID
    disposition: Literal[
        "ADMIT_EXECUTABLE",
        "ADMIT_POSITIVE_GUIDANCE",
        "ADMIT_REFERENCE_ONLY",
        "ADMIT_OBSERVATION_ONLY",
        "ADMIT_ANTI_PATTERN",
        "HOLD_FOR_CORROBORATION",
        "HOLD_FOR_VERSION",
        "HOLD_FOR_LICENSE",
        "HOLD_FOR_SECURITY",
        "REJECT_MALICIOUS",
        "REJECT_IRRELEVANT",
        "REJECT_UNVERIFIABLE",
        "SUPERSEDED",
    ]
    authority_ceiling: Literal[
        "S1_NORMATIVE",
        "S2_FIRST_PARTY",
        "S3_VERIFIED_REGISTRY",
        "S4_MAINTAINED_OSS",
        "S5_MAINTAINER_COMMUNITY",
        "S6_COMMUNITY_CORROBORATED",
        "S7_DISCOVERY_ONLY",
        "S8_UNTRUSTED",
    ]
    allowed_uses: list[
        Literal[
            "DISCOVERY",
            "CORROBORATION",
            "REFERENCE",
            "FAILURE_SIGNATURE",
            "ANTI_PATTERN",
            "NORMATIVE_IMPLEMENTATION",
            "SECURITY_AUTHORITY",
            "EXECUTABLE_ACTIVATION",
        ]
    ]
    forbidden_uses: list[
        Literal[
            "DISCOVERY",
            "CORROBORATION",
            "REFERENCE",
            "FAILURE_SIGNATURE",
            "ANTI_PATTERN",
            "NORMATIVE_IMPLEMENTATION",
            "SECURITY_AUTHORITY",
            "EXECUTABLE_ACTIVATION",
        ]
    ]
    guidance_polarity: Literal["POSITIVE", "ANTI_PATTERN", "OBSERVATION_ONLY"]
    rationale: str
    policy_revision: str
    trial_id: UUID | None = None
    admission_id: UUID | None = None
    resource_id: UUID | None = None
    hold_expires_at: datetime | None = None
    qualified_at: datetime
    created_at: datetime
    updated_at: datetime
