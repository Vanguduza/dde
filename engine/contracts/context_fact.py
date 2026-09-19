# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContextFact(BaseModel):
    """
    EDR-0019 Epic H labelled context fact. The ContextPackage compiler must preserve
    these labels: a model may never receive a MODEL_INFERENCE or UNTRUSTED_EXTERNAL
    claim rendered as though it were settled project fact. Conflict rules are fixed by
    authority_class -- PROJECT_TRUTH outranks QUALIFIED_KNOWLEDGE, VERIFIED_LIVE_STATE
    may supersede a stale runtime observation but never rewrites Project Truth,
    LEARNED_CANDIDATE cannot satisfy a canonical requirement, UNTRUSTED_EXTERNAL may
    trigger discovery but grants no authority, and MODEL_INFERENCE is never persisted as
    fact without explicit promotion.
    """

    model_config = ConfigDict(extra="forbid")

    fact_id: UUID
    tenant_id: UUID
    project_id: UUID
    subject: str
    predicate: str
    value: dict[str, object]
    authority_class: Literal[
        "OWNER_CANONICAL",
        "PROJECT_TRUTH",
        "POLICY_CANONICAL",
        "VERIFIED_LIVE_STATE",
        "VERIFIED_REPOSITORY_STATE",
        "VERIFIED_HISTORY",
        "QUALIFIED_KNOWLEDGE",
        "LEARNED_CANDIDATE",
        "MODEL_INFERENCE",
        "UNTRUSTED_EXTERNAL",
    ]
    source_trust: (
        Literal[
            "S1_NORMATIVE",
            "S2_FIRST_PARTY",
            "S3_VERIFIED_REGISTRY",
            "S4_MAINTAINED_OSS",
            "S5_MAINTAINER_COMMUNITY",
            "S6_COMMUNITY_CORROBORATED",
            "S7_DISCOVERY_ONLY",
            "S8_UNTRUSTED",
        ]
        | None
    ) = None
    source_ref: str | None = None
    valid_from: datetime
    valid_until: datetime | None = None
    observed_at: datetime
    superseded_by_fact_id: UUID | None = None
    supersession_reason: str | None = None
    promoted_from_authority_class: (
        Literal[
            "OWNER_CANONICAL",
            "PROJECT_TRUTH",
            "POLICY_CANONICAL",
            "VERIFIED_LIVE_STATE",
            "VERIFIED_REPOSITORY_STATE",
            "VERIFIED_HISTORY",
            "QUALIFIED_KNOWLEDGE",
            "LEARNED_CANDIDATE",
            "MODEL_INFERENCE",
            "UNTRUSTED_EXTERNAL",
        ]
        | None
    ) = None
    promoted_by_ref: str | None = None
    content_hash: str
    created_at: datetime
    updated_at: datetime
