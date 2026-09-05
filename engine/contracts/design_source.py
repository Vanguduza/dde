# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DesignSource(BaseModel):
    """
    DDE-069 M8 project-scoped source adapter registration and observed health.
    Configuration is metadata only: secrets remain in credential/capability authorities.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    tenant_id: UUID
    project_id: UUID
    provider_key: str
    display_name: str
    source_class: Literal[
        "PROJECT_NATIVE",
        "DDE_LIBRARY",
        "ORGANISATION_LIBRARY",
        "DONOR",
        "EXTERNAL_REGISTRY",
        "MOBILE_REGISTRY",
        "FIGMA",
        "GENERATED",
        "ARCHIVED",
    ]
    adapter_kind: str
    priority: int
    status: Literal[
        "AVAILABLE",
        "DEGRADED",
        "NOT_CONFIGURED",
        "UNAVAILABLE",
        "BLOCKED",
        "DISABLED",
    ]
    health_detail: str | None = None
    capabilities: list[str]
    config: dict[str, object]
    item_count: int | None = None
    last_checked_at: datetime | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
