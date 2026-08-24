# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DonorArtifact(BaseModel):
    """
    Chapter 13.8 Donor Lab ingested external artifact (DDE-046). Rank-9 evidence:
    ingested, never auto-promoted. source_class is the six-value reuse taxonomy; until
    DDE-047's licence classifier lands, ingest persists UNKNOWN (or an explicit caller-
    supplied class that is not OPEN_REUSE without a signed reuse decision). Provenance
    and content_hash make donor influence answerable.
    """

    model_config = ConfigDict(extra="forbid")

    donor_artifact_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    source_uri: str
    content_hash: str
    source_class: Literal[
        "OPEN_REUSE",
        "CONDITIONAL_REUSE",
        "SOURCE_REFERENCE_ONLY",
        "RESTRICTED",
        "UNKNOWN",
        "REJECTED",
    ]
    authority_rank: int
    media_kind: Literal[
        "registry_json",
        "readme",
        "licence_text",
        "source_tree",
        "other",
    ]
    status: Literal["INGESTED", "EXTRACTED", "REJECTED"]
    provenance: dict[str, object]
    feature_dna_id: UUID | None = None
    injection_findings: list[str]
    created_at: datetime
    updated_at: datetime
