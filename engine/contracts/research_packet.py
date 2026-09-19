# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResearchPacket(BaseModel):
    """
    A completeness-gated bundle of research output for one unit revision. A packet
    advances only when every required dimension is covered and source identity,
    provenance, evidence, contradiction status, freshness, relevance, qualification and
    graph-compilation status are all present. Packets may regress: a new contradiction
    or a stale invalidation moves a packet backwards, and that regression is reportable
    rather than hidden.
    """

    model_config = ConfigDict(extra="forbid")

    packet_id: UUID
    tenant_id: UUID
    project_id: UUID
    research_mission_id: UUID
    unit_revision: str
    revision: int
    state: Literal[
        "OPEN",
        "EVIDENCE_PENDING",
        "CONTRADICTION_PENDING",
        "QUALIFICATION_PENDING",
        "GRAPH_PENDING",
        "COMPLETE",
        "REGRESSED",
        "ABANDONED",
    ]
    required_dimensions_covered: list[
        Literal[
            "ARCHITECTURE",
            "OFFICIAL_DOCUMENTATION",
            "CURRENT_RELEASES",
            "SECURITY",
            "FAILURE_MODES",
            "TESTING",
            "PERFORMANCE",
            "DEPLOYMENT",
            "INTEGRATION",
            "UX",
            "FRONTEND_QUALITY",
            "ACCESSIBILITY",
            "SOURCE_INTELLIGENCE",
            "CONTRADICTIONS",
            "ANTI_PATTERNS",
            "WORKFLOW_AUTOMATION",
            "OBSERVABILITY",
            "COMPATIBILITY_MIGRATION",
        ]
    ]
    missing_dimensions: list[
        Literal[
            "ARCHITECTURE",
            "OFFICIAL_DOCUMENTATION",
            "CURRENT_RELEASES",
            "SECURITY",
            "FAILURE_MODES",
            "TESTING",
            "PERFORMANCE",
            "DEPLOYMENT",
            "INTEGRATION",
            "UX",
            "FRONTEND_QUALITY",
            "ACCESSIBILITY",
            "SOURCE_INTELLIGENCE",
            "CONTRADICTIONS",
            "ANTI_PATTERNS",
            "WORKFLOW_AUTOMATION",
            "OBSERVABILITY",
            "COMPATIBILITY_MIGRATION",
        ]
    ]
    finding_refs: list[str]
    conflict_refs: list[str]
    freshness: dict[str, object]
    relevance: dict[str, object]
    graph_compiled: bool
    capsule_compiled: bool
    activation_eligible: bool
    activation_block_reason: str | None = None
    regressed_from_revision: int | None = None
    completeness_hash: str | None = None
    created_at: datetime
    updated_at: datetime
