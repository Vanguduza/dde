# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AgentInteropEndpoint(BaseModel):
    """
    Version-specific provider/harness endpoint discovery and certification authority.
    Discovery is never certification.
    """

    model_config = ConfigDict(extra="forbid")

    endpoint_id: UUID
    tenant_id: UUID
    project_id: UUID
    harness_id: str
    protocol: Literal[
        "NATIVE_CLI",
        "NATIVE_SDK",
        "ACP",
        "MCP",
        "HTTP",
        "OPENAI_COMPATIBLE",
    ]
    executable_or_uri: str
    installation_version: str | None = None
    discovery_state: Literal["UNDISCOVERED", "DISCOVERED", "UNAVAILABLE", "ERROR"]
    certification_state: Literal[
        "DISCOVERED",
        "SMOKE_TESTED",
        "CONTRACT_TESTED",
        "SHADOW",
        "CERTIFIED",
        "STALE",
        "REJECTED",
    ]
    discovered_capabilities: dict[str, object]
    certified_capabilities: dict[str, object]
    certification_refs: list[str]
    health_state: Literal[
        "UNKNOWN",
        "HEALTHY",
        "DEGRADED",
        "UNHEALTHY",
        "AUTH_REQUIRED",
    ]
    config_hash: str | None = None
    last_probe_at: datetime | None = None
    last_error: str | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
