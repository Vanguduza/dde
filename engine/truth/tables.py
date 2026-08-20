"""SQLAlchemy Core tables for Project Truth writes (Chapter 3.3, 3.8).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated from
`schemas/objects/*.json` — the schema is authoritative (Chapter 3.1); this module
only maps the same columns onto SQLAlchemy Core so `engine.truth` can read and
write them inside one PostgreSQL transaction (Chapter 3.5).
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, Integer, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

product_constitution_versions = Table(
    "product_constitution_versions",
    metadata,
    Column("version_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("version", Integer, nullable=False),
    Column("status", Text, nullable=False),
    Column("body_markdown", Text, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("supersedes_id", Uuid(as_uuid=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

requirements = Table(
    "requirements",
    metadata,
    Column("requirement_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("slug", Text, nullable=False),
    Column("statement", Text, nullable=False),
    Column("constraints", JSONB, nullable=False),
    Column("acceptance_conditions", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("supersedes_id", Uuid(as_uuid=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

edrs = Table(
    "edrs",
    metadata,
    Column("edr_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("slug", Text, nullable=False),
    Column("context", Text, nullable=False),
    Column("alternatives", JSONB, nullable=False),
    Column("decision", Text, nullable=False),
    Column("rationale", Text, nullable=False),
    Column("consequences", JSONB, nullable=False),
    Column("affected_requirement_slugs", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("supersedes_id", Uuid(as_uuid=True), nullable=True),
    Column("decided_by_principal", Uuid(as_uuid=True), nullable=True),
    Column("decided_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
