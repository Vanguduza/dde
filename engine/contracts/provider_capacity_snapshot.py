# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProviderCapacitySnapshot(BaseModel):
    """Observed provider capacity/health/quota snapshot used as routing evidence."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: UUID
    tenant_id: UUID
    project_id: UUID
    endpoint_id: UUID
    provider_id: str
    state: Literal[
        "AVAILABLE",
        "DEGRADED",
        "QUOTA_PRESSURE",
        "RATE_LIMITED",
        "EXHAUSTED",
        "COOLDOWN_UNTIL_RESET",
        "REPROMOTION_ELIGIBLE",
        "AUTH_REQUIRED",
        "UNHEALTHY",
    ]
    reset_at: datetime | None = None
    reset_source: str | None = None
    confidence: float
    active_concurrency: int | None = None
    max_concurrency: int | None = None
    latency_ms: int | None = None
    recent_failures: int
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    quota_metadata: dict[str, object]
    observed_at: datetime
    created_at: datetime
    updated_at: datetime
