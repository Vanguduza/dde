"""SQLAlchemy Core table for the Chapter 5.11 failure-attribution engine
(DDE-034).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, generated from
`schemas/objects/failure_attribution.json` -- the schema is authoritative
(Chapter 3.1); this module only maps the same columns onto SQLAlchemy Core
so `engine.attribution` can read and write them inside a shared PostgreSQL
transaction (Chapter 3.5).
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Boolean, Column, MetaData, Numeric, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

failure_attributions = Table(
    "failure_attributions",
    metadata,
    Column("attribution_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("task_attempt_id", Uuid(as_uuid=True), nullable=False),
    Column("verification_run_id", Uuid(as_uuid=True), nullable=False, unique=True),
    Column("outcome", Text, nullable=False),
    Column("category", Text, nullable=False),
    Column("method", Text, nullable=False),
    Column("rule_reasons", JSONB, nullable=False),
    Column("confidence", Numeric, nullable=False),
    Column("eligible_for_promotion_gating", Boolean, nullable=False),
    Column("excluded_from_routing_learning", Boolean, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
