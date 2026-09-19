# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class KnowledgeBorrowGrant(BaseModel):
    """
    EDR-0019 Amendment 1, owner-derived design for the VAN VATI/VTIL borrowing model,
    which the source artifact names but does not specify. Borrowing is COPY-ON-GRANT,
    never a live cross-project read: DDE's tenant/project RLS and the DDE-083 cross-
    project leakage proofs stay intact because the borrower never queries the lender's
    rows. Only OWNER_EXPLICIT authority may authorize a grant. External source trust is
    a property of the source and travels with the copy, but a lender's project-internal
    learning (DDE_LEARNED_RECIPE and other derived material) is not transferable as
    authority and borrows at S7_DISCOVERY_ONLY at best. Revocation invalidates derived
    activations without deleting evidence.
    """

    model_config = ConfigDict(extra="forbid")

    borrow_grant_id: UUID
    tenant_id: UUID
    project_id: UUID
    lender_project_id: UUID
    lender_tenant_id: UUID
    authorized_by_principal_id: UUID | None = None
    authority_class: Literal["OWNER_EXPLICIT"]
    resource_selector: dict[str, object]
    requested_resource_refs: list[str]
    materialized_resource_ids: list[str]
    trust_ceiling: Literal[
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
    includes_derived_learning: bool
    state: Literal[
        "REQUESTED",
        "AUTHORIZED",
        "MATERIALIZED",
        "REVOKED",
        "EXPIRED",
        "REFUSED",
    ]
    refusal_reason: str | None = None
    revocation_reason: str | None = None
    provenance_hash: str
    materialized_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
