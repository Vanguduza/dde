# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Organization(BaseModel):
    """
    Top of the Chapter 13.9 scope chain: Principal -> Organization/Tenant -> Project ->
    Mission -> Task -> runtime bindings. An Organization groups one or more Tenants;
    authorization may be granted at either level (Chapter 14.2 ABAC context).
    """

    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    slug: str
    created_at: datetime
    updated_at: datetime
