# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GraphTrustProjection(BaseModel):
    """
    EDR-0019 Amendment 1. Projects a discovery candidate or qualified resource into the
    existing VEKL knowledge graph while carrying its trust and permitted uses with it,
    so graph retrieval cannot launder a low-trust source into a normative implementation
    slot. This is a projection over `vekl_knowledge_nodes`/`vekl_knowledge_edges`; it
    never becomes a second graph. projected_trust may never exceed the subject's own
    source_trust, and an ANTI_PATTERN or OBSERVATION_ONLY polarity can never satisfy a
    positive implementation slot however strong the graph signal. Revoking the subject
    invalidates the projection without deleting it.
    """

    model_config = ConfigDict(extra="forbid")

    projection_id: UUID
    tenant_id: UUID
    project_id: UUID
    candidate_id: UUID | None = None
    resource_id: UUID | None = None
    knowledge_node_id: UUID | None = None
    subject_kind: Literal["DISCOVERY_CANDIDATE", "VEKL_RESOURCE"]
    projected_trust: Literal[
        "S1_NORMATIVE",
        "S2_FIRST_PARTY",
        "S3_VERIFIED_REGISTRY",
        "S4_MAINTAINED_OSS",
        "S5_MAINTAINER_COMMUNITY",
        "S6_COMMUNITY_CORROBORATED",
        "S7_DISCOVERY_ONLY",
        "S8_UNTRUSTED",
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
    graph_revision: str
    projection_hash: str
    retrievable: bool
    satisfies_positive_slots: bool
    projected_at: datetime
    invalidated_at: datetime | None = None
    invalidation_reason: str | None = None
    created_at: datetime
    updated_at: datetime
