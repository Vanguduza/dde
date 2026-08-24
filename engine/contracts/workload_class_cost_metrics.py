# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WorkloadClassCostMetrics(BaseModel):
    """
    Chapter 16.4 cost per verified success tracked per workload class. Incremented at
    the real RoutingTelemetryService.record_decision_outcome PASSED mutation; regression
    of compile-time overhead tokens blocks context-policy promotion.
    """

    model_config = ConfigDict(extra="forbid")

    metric_id: UUID
    tenant_id: UUID
    project_id: UUID
    workload_class: str
    verified_success_count: int
    total_overhead_tokens: int
    cost_tokens_per_verified_success: float
    created_at: datetime
    updated_at: datetime
