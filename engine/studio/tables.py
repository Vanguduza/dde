"""SQLAlchemy Core tables for the DDE-069 Frontend Studio V2 domain.

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated
from `schemas/objects/*.json` -- the schema is authoritative (Chapter
3.1); this module only maps the same columns onto SQLAlchemy Core so
`engine.studio` can read and write them inside a shared PostgreSQL
transaction (Chapter 3.5).

`engine.studio.contract`, `engine.studio.pxg` and `engine.studio.coverage`
are the sole writers of their respective tables.
"""

from __future__ import annotations

from sqlalchemy import (
    TIMESTAMP,
    Column,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

frontend_contracts = Table(
    "frontend_contracts",
    metadata,
    Column("contract_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=True),
    Column("contract_version", Integer, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("obligations", JSONB, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

pxg_nodes = Table(
    "pxg_nodes",
    metadata,
    Column("node_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("pxg_key", Text, nullable=False),
    Column("node_kind", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("parent_key", Text, nullable=True),
    Column("pxg_revision", Integer, nullable=False),
    Column("source_refs", JSONB, nullable=False),
    Column("attributes", JSONB, nullable=False),
    Column("provenance", JSONB, nullable=False),
    Column("lock_version", Integer, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

pxg_edges = Table(
    "pxg_edges",
    metadata,
    Column("edge_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("from_key", Text, nullable=False),
    Column("to_key", Text, nullable=False),
    Column("edge_kind", Text, nullable=False),
    Column("pxg_revision", Integer, nullable=False),
    Column("attributes", JSONB, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

frontend_coverage_snapshots = Table(
    "frontend_coverage_snapshots",
    metadata,
    Column("snapshot_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("contract_id", Uuid(as_uuid=True), nullable=False),
    Column("contract_version", Integer, nullable=False),
    Column("pxg_revision", Integer, nullable=False),
    Column("summary_state", Text, nullable=False),
    Column("weighted_percent", Numeric, nullable=True),
    Column("dimensions", JSONB, nullable=False),
    Column("findings", JSONB, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

frontend_locks = Table(
    "frontend_locks",
    metadata,
    Column("lock_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("lock_kind", Text, nullable=False),
    Column("scope_key", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("created_by", Uuid(as_uuid=True), nullable=False),
    Column("released_by", Uuid(as_uuid=True), nullable=True),
    Column("released_at", TIMESTAMP(timezone=True), nullable=True),
    Column("lock_version", Integer, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

frontend_candidates = Table(
    "frontend_candidates",
    metadata,
    Column("candidate_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=True),
    Column("workspace_id", Uuid(as_uuid=True), nullable=True),
    Column("title", Text, nullable=False),
    Column("state", Text, nullable=False),
    Column("origin", Text, nullable=False),
    Column("base_pxg_revision", Integer, nullable=False),
    Column("base_contract_version", Integer, nullable=True),
    Column("scope_keys", JSONB, nullable=False),
    Column("verification_run_id", Uuid(as_uuid=True), nullable=True),
    Column("provenance", JSONB, nullable=False),
    Column("state_detail", Text, nullable=True),
    Column("superseded_by", Uuid(as_uuid=True), nullable=True),
    Column("promoted_at", TIMESTAMP(timezone=True), nullable=True),
    Column("lock_version", Integer, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

frontend_mutations = Table(
    "frontend_mutations",
    metadata,
    Column("mutation_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("candidate_id", Uuid(as_uuid=True), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("operation", Text, nullable=False),
    Column("target_key", Text, nullable=False),
    Column("origin", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("inverse", JSONB, nullable=False),
    Column("preconditions", JSONB, nullable=False),
    Column("refusal_code", Text, nullable=True),
    Column("refusal_detail", Text, nullable=True),
    Column("reverted_by", Uuid(as_uuid=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
