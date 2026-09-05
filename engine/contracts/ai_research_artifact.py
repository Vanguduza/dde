# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResearchSource(BaseModel):
    """ResearchSource nested contract."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_kind: Literal["WEB", "FILE", "REPOSITORY", "DDE_TRUTH", "DATABASE", "HUMAN"]
    ref: str
    title: str | None = None
    authority: Literal["PRIMARY", "SECONDARY", "COMMUNITY", "INTERNAL", "UNKNOWN"]
    published_at: datetime | None = None
    retrieved_at: datetime
    content_hash: str | None = None
    notes: str | None = None


class AiResearchArtifact(BaseModel):
    """
    Cited deep-research/compare/council artifact with preserved sources, hypotheses and
    unresolved questions.
    """

    model_config = ConfigDict(extra="forbid")

    research_id: UUID
    tenant_id: UUID
    project_id: UUID
    conversation_id: UUID
    mission_id: UUID | None = None
    created_from_turn_id: UUID | None = None
    mode: Literal["DEEP_RESEARCH", "COMPARE", "COUNCIL"]
    question: str
    scope: dict[str, object]
    state: Literal[
        "DRAFT",
        "RESEARCHING",
        "SYNTHESIZING",
        "COMPLETED",
        "BLOCKED",
        "CANCELLED",
    ]
    source_ledger: list[ResearchSource]
    findings: list[dict[str, object]]
    hypotheses: list[dict[str, object]]
    unresolved_questions: list[str]
    confidence: float | None = None
    result_refs: list[str]
    lock_version: int
    created_at: datetime
    updated_at: datetime
