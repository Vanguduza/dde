# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AttentionCandidate(BaseModel):
    """
    EDR-0019 Epic I pre-item attention candidate. This does not replace attention_items:
    the existing governance attention_items table remains the durable attention
    authority, and a candidate is the scored, deduplicated proposal that may become one.
    Deduplication is by dedupe_key, so a repeating failure collapses into one item with
    a repeat count instead of flooding the operator. Security and owner-approval classes
    bypass the non-urgent budget; everything else is budgeted.
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    attention_class: Literal[
        "INFO",
        "FOLLOW_UP",
        "BLOCKER",
        "APPROVAL",
        "SECURITY",
        "DRIFT",
        "URGENT",
    ]
    dedupe_key: str
    summary: str
    source_event_ref: str | None = None
    importance: float
    urgency: float
    actionability: float
    novelty: float
    confidence: float
    blast_radius: float
    time_sensitivity: float
    owner_required: bool
    repeat_penalty: float
    score: float
    repeat_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    disposition: Literal[
        "PENDING",
        "PROMOTED",
        "SUPPRESSED_BUDGET",
        "SUPPRESSED_DUPLICATE",
        "SUPPRESSED_QUIET_HOURS",
        "SNOOZED",
        "EXPIRED",
    ]
    bypassed_budget: bool
    attention_id: UUID | None = None
    snoozed_until: datetime | None = None
    created_at: datetime
    updated_at: datetime
