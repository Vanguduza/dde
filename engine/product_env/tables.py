"""Chapter 11.6 ProductEnvironment + SeedDataset persistence.

Hand-written SQLAlchemy Core mirror of
`schemas/objects/{product_environment,seed_dataset}.json` (the schema is
authoritative, Chapter 3.1) plus migration 0012's DDL. Owned by the
verification domain per Chapter 3.6/3.8 ("oracle, runners, product envs");
this module tree lives under `engine.product_env` so the lifecycle service,
seed registry and migration verifier stay one cohesive unit.
"""

from __future__ import annotations

from sqlalchemy import (
    TIMESTAMP,
    Column,
    Integer,
    MetaData,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

seed_datasets = Table(
    "seed_datasets",
    metadata,
    Column("dataset_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("slug", Text, nullable=False),
    Column("version", Integer, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("artifact_ref", Text, nullable=False),
    Column("supersedes_dataset_id", Uuid(as_uuid=True), nullable=True),
    Column("status", Text, nullable=False),
    Column("created_by", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
)

product_environments = Table(
    "product_environments",
    metadata,
    Column("product_env_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=True),
    Column("class", Text, nullable=False),
    Column("source_revision", Text, nullable=False),
    Column("build_artifact_ref", Text, nullable=False),
    Column("runtime_topology_ref", JSONB, nullable=False),
    Column("datastore_ref", Text, nullable=False),
    Column("seed_dataset_id", Uuid(as_uuid=True), nullable=True),
    Column("migration_state", Text, nullable=False),
    Column(
        "migration_verification",
        JSONB,
        nullable=True,
    ),
    Column("base_url", Text, nullable=True),
    Column("credentials_profile_id", Uuid(as_uuid=True), nullable=True),
    Column("status", Text, nullable=False),
    Column("ttl_expires_at", TIMESTAMP(timezone=True), nullable=True),
    Column("failure_snapshot", JSONB, nullable=True),
    Column("idempotency_key", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
