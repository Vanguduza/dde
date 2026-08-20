"""SQLAlchemy Core tables for Worker Manager persistence (Chapter 3.3, 3.8).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated
from `schemas/objects/{worker_run,worker_event}.json` — the schema is
authoritative (Chapter 3.1); this module only maps the same columns onto
SQLAlchemy Core so `engine.workers` can read and write them inside a shared
PostgreSQL transaction (Chapter 3.5).

`worker_events` is declaratively partitioned by `occurred_at` (Chapter 3.7);
SQLAlchemy Core addresses it as one logical table through the parent
partition root, exactly as `engine.events.tables` does for `events`.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, Integer, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

worker_runs = Table(
    "worker_runs",
    metadata,
    Column("run_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_attempt_id", Uuid(as_uuid=True), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("execution_plan_id", Uuid(as_uuid=True), nullable=False),
    Column("worker_session_id", Uuid(as_uuid=True), nullable=True),
    Column("worker_id", Text, nullable=False),
    Column("worker_profile_id", Text, nullable=False),
    Column("environment_id", Uuid(as_uuid=True), nullable=False),
    Column("workspace_id", Uuid(as_uuid=True), nullable=False),
    Column("context_package_id", Uuid(as_uuid=True), nullable=False),
    Column("policy_version", Text, nullable=False),
    Column("lease_set_hash", Text, nullable=False),
    Column("checkpoint_id", Uuid(as_uuid=True), nullable=True),
    Column("status", Text, nullable=False),
    Column("failure_class", Text, nullable=True),
    Column("usage_record_id", Uuid(as_uuid=True), nullable=True),
    Column("artifact_manifest_id", Uuid(as_uuid=True), nullable=True),
    Column("started_at", TIMESTAMP(timezone=True), nullable=True),
    Column("ended_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

worker_events = Table(
    "worker_events",
    metadata,
    Column("event_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("run_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("event_type", Text, nullable=False),
    Column("occurred_at", TIMESTAMP(timezone=True), primary_key=True),
    Column("actor", Text, nullable=False),
    Column("correlation_id", Text, nullable=False),
    Column("causation_id", Text, nullable=True),
    Column("payload", JSONB, nullable=False),
    Column("schema_version", Text, nullable=False),
    Column("integrity_hash", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
