# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProviderModelAvailability(BaseModel):
    """
    EDR-0019 Amendment 1. Observed catalogue of the models a provider actually exposes.
    This is discovery evidence only and never promotion: catalogue presence, a free-tier
    label or a vendor announcement does not make a model routable, exactly as DEV_PLAN
    20A already states for the OpenAI catalogue. Routing eligibility still requires a
    ProviderReadinessSnapshot at READY with a live probe and attested identity, so
    `attested` here records only that the provider named this model, not that DDE ran
    it.
    """

    model_config = ConfigDict(extra="forbid")

    availability_id: UUID
    tenant_id: UUID
    project_id: UUID
    provider_id: str
    model_identity: str
    harness_id: str | None = None
    discovered_via: Literal["LIVE_CATALOGUE", "METADATA_PROBE", "OPERATOR_DECLARED"]
    available: bool
    deprecated: bool
    attested: bool
    context_window: int | None = None
    supports_tools: bool | None = None
    supports_streaming: bool | None = None
    cost_metadata: dict[str, object]
    readiness_snapshot_id: UUID | None = None
    evidence_pointer: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
