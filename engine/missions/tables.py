"""SQLAlchemy Core tables for Mission Kernel persistence (Chapter 3.3, 3.8).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated from
`schemas/objects/{mission,task}.json` — the schema is authoritative
(Chapter 3.1); this module only maps the same columns onto SQLAlchemy Core so
`engine.missions` can read and write them inside a shared PostgreSQL
transaction (Chapter 3.5).

Chapter 3.8's object ownership matrix lists `Mission` and `Task`'s owner
module as `missions`; `TaskGraph`/`TaskGraphEdge` are owned by
`engine.planning` (see `engine/planning/tables.py`) — this module used to
also define them as a flagged, intentional DDE-006 divergence, corrected
here to match the blueprint.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

missions = Table(
    "missions",
    metadata,
    Column("mission_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("slug", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("intent", Text, nullable=False),
    Column("success_definition", Text, nullable=False),
    Column("scope", JSONB, nullable=False),
    Column("requirement_refs", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("autonomy_ceiling", Integer, nullable=False),
    Column("lock_version", Integer, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

tasks = Table(
    "tasks",
    metadata,
    Column("task_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("graph_id", Uuid(as_uuid=True), nullable=False),
    Column("parent_task_id", Uuid(as_uuid=True), nullable=True),
    Column("title", Text, nullable=False),
    Column("intent", Text, nullable=False),
    Column("task_class", Text, nullable=False),
    Column("requirement_refs", JSONB, nullable=False),
    Column("feature_refs", JSONB, nullable=False),
    Column("success_criteria", JSONB, nullable=False),
    Column("expected_write_scope", JSONB, nullable=False),
    Column("expected_read_scope", JSONB, nullable=False),
    Column("blast_radius", Text, nullable=False),
    Column("risk_class", Text, nullable=False),
    Column("estimated_effort", Text, nullable=False),
    Column("autonomy_ceiling", Integer, nullable=False),
    Column("requires_approval", Boolean, nullable=False),
    Column("verification_profile_ref", Text, nullable=True),
    Column("status", Text, nullable=False),
    Column("lock_version", Integer, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
