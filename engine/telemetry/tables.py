"""SQLAlchemy Core table for the Chapter 6.5 real-telemetry engine
(DDE-035).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, generated from
`schemas/objects/routing_decision_outcome.json` -- the schema is
authoritative (Chapter 3.1); this module only maps the same columns onto
SQLAlchemy Core so `engine.telemetry` can read and write them inside a
shared PostgreSQL transaction (Chapter 3.5).
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

routing_decision_outcomes = Table(
    "routing_decision_outcomes",
    metadata,
    Column("outcome_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("route_decision_id", Uuid(as_uuid=True), nullable=False),
    Column("task_attempt_id", Uuid(as_uuid=True), nullable=False),
    Column("verification_run_id", Uuid(as_uuid=True), nullable=False, unique=True),
    Column("actual_verified_outcome", Text, nullable=False),
    Column("verification_confidence", Numeric, nullable=False),
    Column("rework_count", Integer, nullable=False),
    Column("escalated", Boolean, nullable=False),
    Column("human_intervention_required", Boolean, nullable=False),
    Column("recovery_action", Text, nullable=True),
    Column("failure_class", Text, nullable=True),
    Column("elapsed_seconds", Numeric, nullable=True),
    Column("context_package_id", Uuid(as_uuid=True), nullable=False),
    Column("capability_set", JSONB, nullable=False),
    Column("failure_attribution_id", Uuid(as_uuid=True), nullable=True),
    Column("disclosed_gaps", JSONB, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
