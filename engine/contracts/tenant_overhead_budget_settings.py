# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TenantOverheadBudgetSettings(BaseModel):
    """
    Chapter 16.4 per-tenant hard cap configuration for control-plane overhead token-
    share budgets.
    """

    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    hard_cap_overhead_token_share: float
    created_at: datetime
    updated_at: datetime
