"""SQLAlchemy Core tables for the event store, outbox and command ledger
(Chapter 3.3, 3.7).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated from
`schemas/objects/{event,outbox,command_idempotency}.json` — the schema is
authoritative (Chapter 3.1); this module only maps the same columns onto
SQLAlchemy Core so `engine.events` can read and write them inside a shared
PostgreSQL transaction (Chapter 3.5).

`events` is declaratively partitioned by `occurred_at` in PostgreSQL (Chapter
3.7); SQLAlchemy Core addresses it as one logical table through the parent
partition root, exactly as `engine.audit.tables` does for the (unpartitioned)
`audit_events` table.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, Integer, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

events = Table(
    "events",
    metadata,
    Column("event_id", Uuid(as_uuid=True), primary_key=True),
    Column("event_type", Text, nullable=False),
    Column("aggregate_type", Text, nullable=False),
    Column("aggregate_id", Uuid(as_uuid=True), nullable=False),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=True),
    Column("task_id", Uuid(as_uuid=True), nullable=True),
    Column("sequence", Integer, nullable=False),
    Column("occurred_at", TIMESTAMP(timezone=True), primary_key=True),
    Column("correlation_id", Text, nullable=False),
    Column("causation_id", Text, nullable=True),
    Column("payload", JSONB, nullable=False),
    Column("schema_version", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

outbox = Table(
    "outbox",
    metadata,
    Column("outbox_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=True),
    Column("event_id", Uuid(as_uuid=True), nullable=False),
    Column("status", Text, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("published_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

command_idempotency = Table(
    "command_idempotency",
    metadata,
    Column("command_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("idempotency_key", Text, nullable=False),
    Column("request_hash", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("result", JSONB, nullable=True),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
