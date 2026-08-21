"""SQLAlchemy Core tables for Chapter 13 governance objects.

Hand-written to mirror `schemas/sql/0001_stage1.sql`, generated from
`schemas/objects/approval.json`, `standing_approval.json`, and
`attention_item.json`.
"""

from __future__ import annotations

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
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

approvals = Table(
    "approvals",
    metadata,
    Column("approval_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=True),
    Column("approval_type", Text, nullable=False),
    Column("scope_hash", Text, nullable=False),
    Column("requested_by", Uuid(as_uuid=True), nullable=False),
    Column("required_role", Text, nullable=False),
    Column("evidence_refs", JSONB, nullable=False),
    Column("suggested_decision", Text, nullable=True),
    Column("status", Text, nullable=False),
    Column("decided_by", Uuid(as_uuid=True), nullable=True),
    Column("decided_at", TIMESTAMP(timezone=True), nullable=True),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=True),
    Column("rationale", Text, nullable=True),
    Column("standing_id", Uuid(as_uuid=True), nullable=True),
    Column("edr_id", Uuid(as_uuid=True), nullable=True),
    Column("human_minutes", Numeric, nullable=False),
    Column("command_id", Uuid(as_uuid=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

standing_approvals = Table(
    "standing_approvals",
    metadata,
    Column("standing_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=True),
    Column("approval_types", JSONB, nullable=False),
    Column("blast_radius_ceiling", Text, nullable=False),
    Column("risk_ceiling", Text, nullable=False),
    Column("cost_ceiling", Numeric, nullable=False),
    Column("task_count_ceiling", Integer, nullable=False),
    Column("path_scope", JSONB, nullable=False),
    Column("forbidden_operations", JSONB, nullable=False),
    Column("valid_from", TIMESTAMP(timezone=True), nullable=False),
    Column("valid_until", TIMESTAMP(timezone=True), nullable=False),
    Column("revocable_immediately", Boolean, nullable=False),
    Column("granted_by", Uuid(as_uuid=True), nullable=False),
    Column("rationale", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("task_count_used", Integer, nullable=False),
    Column("cost_used", Numeric, nullable=False),
    Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
    Column("command_id", Uuid(as_uuid=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

attention_items = Table(
    "attention_items",
    metadata,
    Column("attention_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("kind", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("approval_id", Uuid(as_uuid=True), nullable=True),
    Column("standing_id", Uuid(as_uuid=True), nullable=True),
    Column("sla_due_at", TIMESTAMP(timezone=True), nullable=False),
    Column("opened_at", TIMESTAMP(timezone=True), nullable=False),
    Column("acknowledged_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
