# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MigrationVerification(BaseModel):
    """MigrationVerification nested contract."""

    model_config = ConfigDict(extra="forbid")

    forward_empty: dict[str, object]
    forward_previous: dict[str, object]


class FailureSnapshot(BaseModel):
    """FailureSnapshot nested contract."""

    model_config = ConfigDict(extra="forbid")

    snapshot_ref: str
    content_hash: str
    captured_at: datetime


class ProductEnvironment(BaseModel):
    """
    Chapter 11.6 throwaway deployment of the software DDE builds, used to verify it.
    Distinct from ExecutionEnvironment, which is where workers run. Lifecycle only per
    Chapter 3.8's ownership matrix (owner engine.verification): PROVISIONING ->
    MIGRATING -> SEEDING -> READY -> IN_USE -> TEARDOWN, plus FAILED reachable from
    every pre-terminal state. Every ephemeral_preview carries a TTL and is destroyed on
    expiry; production rows are never provisioned by a worker and never reachable from
    an ExecutionEnvironment.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    product_env_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    class_: Literal[
        "ephemeral_preview",
        "integration",
        "staging",
        "production",
    ] = Field(alias="class")
    source_revision: str
    build_artifact_ref: str
    runtime_topology_ref: dict[str, object]
    datastore_ref: str
    seed_dataset_id: UUID | None = None
    migration_state: Literal[
        "PENDING_BASELINE",
        "BASELINE_APPLIED",
        "FORWARD_VERIFIED_EMPTY",
        "FORWARD_VERIFIED_PREVIOUS_SCHEMA",
        "FORWARD_FAILED",
    ]
    migration_verification: MigrationVerification | None = None
    base_url: str | None = None
    credentials_profile_id: UUID | None = None
    status: Literal[
        "PROVISIONING",
        "MIGRATING",
        "SEEDING",
        "READY",
        "IN_USE",
        "TEARDOWN",
        "FAILED",
    ]
    ttl_expires_at: datetime | None = None
    failure_snapshot: FailureSnapshot | None = None
    idempotency_key: str
    created_at: datetime
    updated_at: datetime
