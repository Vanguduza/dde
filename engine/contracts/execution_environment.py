# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExecutionEnvironment(BaseModel):
    """Worker execution environment. Optimistic locking required by Chapter 3.5."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    environment_id: UUID
    tenant_id: UUID
    project_id: UUID
    class_: Literal[
        "research",
        "development",
        "security",
        "staging",
        "production",
    ] = Field(alias="class")
    type: Literal[
        "local",
        "docker",
        "microvm",
        "vm",
        "device",
        "ci_runner",
        "remote_api",
    ]
    os_family: str
    architecture: str
    runtime_image: str
    image_digest: str
    toolchain_manifest: dict[str, object]
    toolchain_manifest_hash: str
    resource_limits: dict[str, object]
    network_policy: dict[str, object]
    filesystem_policy: dict[str, object]
    isolation_level: Literal["process", "container", "gvisor", "microvm"]
    credential_profile_id: UUID | None = None
    security_profile_id: UUID | None = None
    capability_compatibility: dict[str, object]
    worker_compatibility: dict[str, object]
    status: str
    health_status: str
    lifecycle_state: Literal[
        "PROVISIONING",
        "READY",
        "ACTIVE",
        "DRAINING",
        "RETIRED",
        "FAILED",
        "REPAIRING",
        "REPLACEMENT",
    ]
    lock_version: int
    created_at: datetime
    updated_at: datetime
