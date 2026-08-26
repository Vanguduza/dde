"""SQLAlchemy Core table for the Chapter 6.8 ExperienceRecord engine
(DDE-057).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, generated from
`schemas/objects/experience_record.json` -- the schema is authoritative
(Chapter 3.1); this module only maps the same columns onto SQLAlchemy
Core so `engine.learning` can read and write them inside a shared
PostgreSQL transaction (Chapter 3.5).
"""

from __future__ import annotations

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    MetaData,
    Numeric,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

experience_records = Table(
    "experience_records",
    metadata,
    Column("experience_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=True),
    Column("task_id", Uuid(as_uuid=True), nullable=True),
    Column("route_decision_id", Uuid(as_uuid=True), nullable=True),
    Column("task_attempt_id", Uuid(as_uuid=True), nullable=True),
    Column("verification_run_id", Uuid(as_uuid=True), nullable=True, unique=True),
    Column("routing_simulation_run_id", Uuid(as_uuid=True), nullable=True, unique=True),
    Column("outcome_id", Uuid(as_uuid=True), nullable=True),
    Column("experience_origin", Text, nullable=False),
    Column("routing_policy_version", Text, nullable=False),
    Column("candidate_set_hash", Text, nullable=False),
    Column("selection_propensity", Numeric, nullable=False),
    Column("prediction_vector", JSONB, nullable=False),
    Column("observed_outcome_vector", JSONB, nullable=False),
    Column("verification_confidence", Numeric, nullable=False),
    Column("failure_attribution", Text, nullable=False),
    Column("attribution_confidence", Numeric, nullable=False),
    Column("holdout_partition", Text, nullable=False),
    Column("promotion_evidence_refs", JSONB, nullable=False),
    Column("drift_snapshot_id", Uuid(as_uuid=True), nullable=True),
    Column("learning_run_id", Uuid(as_uuid=True), nullable=True),
    Column("eligible_for_routing_training", Boolean, nullable=False),
    Column("eligibility_reasons", JSONB, nullable=False),
    Column("down_weighted", Boolean, nullable=False),
    Column("promotion_state", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
