# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResearchMission(BaseModel):
    """
    EDR-0019 Epic D ahead-of-work research mission. Advisory only: a research mission
    may prepare knowledge for upcoming Development Units but may never reorder the
    TaskGraph, create implementation tasks, expand product scope or amend Project Truth.
    Restart is idempotent from the mission's ResearchCursor; mission_definition_hash
    pins the coverage definition so a redefinition is a new mission rather than a silent
    mutation.
    """

    model_config = ConfigDict(extra="forbid")

    research_mission_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    unit_map_id: UUID | None = None
    title: str
    required_dimensions: list[
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
    optional_dimensions: list[
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
    target_unit_revisions: list[str]
    status: Literal["DRAFT", "ACTIVE", "PAUSED", "COMPLETE", "ABANDONED", "SUPERSEDED"]
    mission_definition_hash: str
    coverage_hash: str | None = None
    policy_revision: str
    budget: dict[str, object]
    egress_profile: str
    cells_total: int
    cells_complete: int
    cells_conflicted: int
    created_at: datetime
    updated_at: datetime
