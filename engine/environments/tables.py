"""SQLAlchemy Core table for ExecutionEnvironment persistence (Chapter 3.3,
3.8). Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is
generated from `schemas/objects/execution_environment.json` — the schema is
authoritative (Chapter 3.1); this module only maps the same columns onto
SQLAlchemy Core so `engine.environments` can read and write them inside a
shared PostgreSQL transaction (Chapter 3.5).

Chapter 3.8's object ownership matrix lists ExecutionEnvironment's owner
module as `environments`, created by the Provisioner; this module (and
`engine.environments.repository`/`engine.environments.service`) is that sole
writer.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, Integer, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

execution_environments = Table(
    "execution_environments",
    metadata,
    Column("environment_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("class", Text, nullable=False),
    Column("type", Text, nullable=False),
    Column("os_family", Text, nullable=False),
    Column("architecture", Text, nullable=False),
    Column("runtime_image", Text, nullable=False),
    Column("image_digest", Text, nullable=False),
    Column("toolchain_manifest", JSONB, nullable=False),
    Column("toolchain_manifest_hash", Text, nullable=False),
    Column("resource_limits", JSONB, nullable=False),
    Column("network_policy", JSONB, nullable=False),
    Column("filesystem_policy", JSONB, nullable=False),
    Column("isolation_level", Text, nullable=False),
    Column("credential_profile_id", Uuid(as_uuid=True), nullable=True),
    Column("security_profile_id", Uuid(as_uuid=True), nullable=True),
    Column("capability_compatibility", JSONB, nullable=False),
    Column("worker_compatibility", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("health_status", Text, nullable=False),
    Column("lifecycle_state", Text, nullable=False),
    Column("lock_version", Integer, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
