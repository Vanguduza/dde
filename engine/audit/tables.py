"""SQLAlchemy Core table for the audit ledger (Chapter 3.3, 3.7).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated from
`schemas/objects/audit_event.json` — the schema is authoritative (Chapter
3.1); this module only maps the same columns onto SQLAlchemy Core so
`engine.audit` can read and write them inside a shared PostgreSQL
transaction (Chapter 3.5).
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, Integer, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

audit_events = Table(
    "audit_events",
    metadata,
    Column("audit_event_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=True),
    Column("event_type", Text, nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("prev_hash", Text, nullable=True),
    Column("entry_hash", Text, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
