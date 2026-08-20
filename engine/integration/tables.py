"""SQLAlchemy Core tables for merge-queue persistence (Chapter 3.3, 3.8).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated from
`schemas/objects/{write_scope_lease,integration_proposal}.json` -- the schema
is authoritative (Chapter 3.1); this module only maps the same columns onto
SQLAlchemy Core so `engine.integration` can read and write them inside a
shared PostgreSQL transaction (Chapter 3.5).

Chapter 3.8's ownership matrix lists both `WriteScopeLease` and (by Chapter
3.6's repository layout, "merge queue + write scopes") `IntegrationProposal`
under `engine.integration`.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

write_scope_leases = Table(
    "write_scope_leases",
    metadata,
    Column("lease_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("scope_patterns", JSONB, nullable=False),
    Column("exclusive", Boolean, nullable=False),
    Column("status", Text, nullable=False),
    Column("acquired_at", TIMESTAMP(timezone=True), nullable=False),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
    Column("released_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

integration_proposals = Table(
    "integration_proposals",
    metadata,
    Column("proposal_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("task_attempt_id", Uuid(as_uuid=True), nullable=False),
    Column("source_branch", Text, nullable=False),
    Column("base_revision", Text, nullable=False),
    Column("proposed_revision", Text, nullable=False),
    Column("diff_summary", Text, nullable=False),
    Column("changed_paths", JSONB, nullable=False),
    Column("scope_lease_id", Uuid(as_uuid=True), nullable=False),
    Column("pre_integration_verification_ref", Uuid(as_uuid=True), nullable=False),
    Column("status", Text, nullable=False),
    Column("conflict_class", Text, nullable=True),
    Column("attempts", Integer, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
