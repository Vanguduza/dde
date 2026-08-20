"""SQLAlchemy Core table for Workspace persistence (Chapter 3.3, 3.8).
Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated
from `schemas/objects/workspace.json` — the schema is authoritative
(Chapter 3.1); this module only maps the same columns onto SQLAlchemy Core
so `engine.workspaces` can read and write them inside a shared PostgreSQL
transaction (Chapter 3.5).

Chapter 3.8 lists Workspace's owner module as `workspaces`, created by the
Execution Planner; this module (and `engine.workspaces.repository`/
`engine.workspaces.service`) is that sole writer.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, Integer, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

workspaces = Table(
    "workspaces",
    metadata,
    Column("workspace_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=True),
    Column("task_id", Uuid(as_uuid=True), nullable=True),
    Column("execution_environment_id", Uuid(as_uuid=True), nullable=True),
    Column("base_revision", Text, nullable=True),
    Column("current_revision", Text, nullable=True),
    Column("workspace_path", Text, nullable=True),
    Column("policy", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("lock_version", Integer, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
