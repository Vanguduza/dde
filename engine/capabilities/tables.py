"""SQLAlchemy Core table for capability registry persistence (Chapter 3.3,
3.8's `capabilities` global registry -- see `schemas/objects/
capability_descriptor.json`'s `x-dde-storage`).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated from
`schemas/objects/capability_descriptor.json` -- the schema is authoritative
(Chapter 3.1); this module only maps the same columns onto SQLAlchemy Core so
`engine.capabilities` can read and write them inside a shared PostgreSQL
transaction (Chapter 3.5).

Unlike every other Stage 1/2 table, `capabilities` carries no `tenant_id`/
`project_id` columns -- Chapter 3.2 names it a global registry, tenant-
agnostic by design, scoped instead by `visibility`/`owner_tenant_id`
(enforced by a matching RLS predicate, `schemas/sql/0001_stage1.sql`'s
`capabilities_tenant_isolation` policy).
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

capabilities = Table(
    "capabilities",
    metadata,
    Column("descriptor_id", Uuid(as_uuid=True), primary_key=True),
    Column("capability_id", Text, nullable=False),
    Column("version", Text, nullable=False),
    Column("category", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("interface_schema_ref", Text, nullable=True),
    Column("input_schema_ref", Text, nullable=True),
    Column("output_schema_ref", Text, nullable=True),
    Column("implementations", JSONB, nullable=False),
    Column("supported_worker_profiles", JSONB, nullable=False),
    Column("supported_environments", JSONB, nullable=False),
    Column("supported_workloads", JSONB, nullable=False),
    Column("risk_class", Text, nullable=False),
    Column("side_effect_class", Text, nullable=False),
    Column("enforcement_tier", Text, nullable=False),
    Column("permission_model", JSONB, nullable=False),
    Column("cost_model", JSONB, nullable=False),
    Column("network_requirements", JSONB, nullable=False),
    Column("dependencies", JSONB, nullable=False),
    Column("provenance", JSONB, nullable=False),
    Column("certification_status", Text, nullable=False),
    Column("lifecycle_status", Text, nullable=False),
    Column("visibility", Text, nullable=False),
    Column("owner_tenant_id", Uuid(as_uuid=True), nullable=True),
    Column("supersedes_descriptor_id", Uuid(as_uuid=True), nullable=True),
    Column("superseded_by_descriptor_id", Uuid(as_uuid=True), nullable=True),
    Column("descriptor_hash", Text, nullable=False),
    Column("registered_by", Text, nullable=False),
    Column("deprecated_at", TIMESTAMP(timezone=True), nullable=True),
    Column("retired_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
