"""SQLAlchemy Core tables for Verification persistence (Chapter 3.3, 3.8).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated from
`schemas/objects/{acceptance_oracle,verification_run}.json` -- the schema is
authoritative (Chapter 3.1); this module only maps the same columns onto
SQLAlchemy Core so `engine.verification` can read and write them inside a
shared PostgreSQL transaction (Chapter 3.5).

Chapter 3.8 lists `AcceptanceOracle`'s definition among the immutable
objects of Chapter 3.10 and does not give it its own ownership-matrix row;
Chapter 3.6's repository layout puts "oracle, runners, product envs" under
`engine.verification`, which is the ownership this module encodes.
`VerificationRun` and `Evidence` (`engine/verification/repository.py`) are
both owned by `verification` per Chapter 3.8's matrix.
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

acceptance_oracles = Table(
    "acceptance_oracles",
    metadata,
    Column("oracle_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=True),
    Column("oracle_version", Text, nullable=False),
    Column("scope", Text, nullable=False),
    Column("requirement_refs", JSONB, nullable=False),
    Column("feature_refs", JSONB, nullable=False),
    Column("observable_outcomes", JSONB, nullable=False),
    Column("domain_invariants", JSONB, nullable=False),
    Column("negative_cases", JSONB, nullable=False),
    Column("minimum_confidence", Numeric, nullable=False),
    Column("human_assertions", JSONB, nullable=False),
    Column("approved_by", Text, nullable=True),
    Column("approved_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

mission_oracle_evaluations = Table(
    "mission_oracle_evaluations",
    metadata,
    Column("evaluation_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("oracle_id", Uuid(as_uuid=True), nullable=False),
    Column("workspace_id", Uuid(as_uuid=True), nullable=False),
    Column("status", Text, nullable=False),
    Column("task_oracle_verdict", Text, nullable=False),
    Column("check_results", JSONB, nullable=False, server_default="[]"),
    Column("outcome_results", JSONB, nullable=False, server_default="[]"),
    Column("recovery_decision", JSONB, nullable=True),
    Column("learning_signal_class", Text, nullable=False),
    Column("excluded_from_routing_learning", Boolean, nullable=False),
    Column("disclosed_gaps", JSONB, nullable=False, server_default="[]"),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

verification_runs = Table(
    "verification_runs",
    metadata,
    Column("verification_run_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("task_attempt_id", Uuid(as_uuid=True), nullable=False),
    Column("worker_run_id", Uuid(as_uuid=True), nullable=False),
    Column("workspace_id", Uuid(as_uuid=True), nullable=False),
    Column("oracle_id", Uuid(as_uuid=True), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("status", Text, nullable=False),
    Column("confidence", Numeric, nullable=False),
    Column("check_results", JSONB, nullable=False),
    Column("outcome_results", JSONB, nullable=False),
    Column("negative_case_results", JSONB, nullable=False),
    Column("evidence_refs", JSONB, nullable=False),
    Column("started_at", TIMESTAMP(timezone=True), nullable=False),
    Column("ended_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

evidence = Table(
    "evidence",
    metadata,
    Column("evidence_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("verification_run_id", Uuid(as_uuid=True), nullable=False),
    Column("integrated_revision", Text, nullable=False),
    Column("oracle_id", Uuid(as_uuid=True), nullable=True),
    Column("outcome_id", Uuid(as_uuid=True), nullable=True),
    Column("evidence_type", Text, nullable=False),
    Column("artifact_refs", JSONB, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("signature", Text, nullable=False),
    Column("produced_by", Text, nullable=False),
    Column("independence_flags", JSONB, nullable=False),
    Column("recorded_at", TIMESTAMP(timezone=True), nullable=False),
    Column("status", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
