"""SQLAlchemy Core tables for Chapter 5.13 eval corpus persistence
(Chapter 3.3, 3.8): `eval_cases` and `promotion_gate_runs`.

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated
from `schemas/objects/eval_case.json` / `schemas/objects/promotion_gate_run.json`
-- the schema is authoritative (Chapter 3.1); this module only maps the
same columns onto SQLAlchemy Core so `engine.context` can read and write
them inside a shared PostgreSQL transaction (Chapter 3.5).
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

eval_cases = Table(
    "eval_cases",
    metadata,
    Column("eval_case_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("source_mission_id", Uuid(as_uuid=True), nullable=False),
    Column("source_task_id", Uuid(as_uuid=True), nullable=False),
    Column("source_proposal_id", Uuid(as_uuid=True), nullable=False),
    Column("task_class", Text, nullable=False),
    Column("is_adversarial", Boolean, nullable=False),
    Column("required_refs", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("frozen_version", Integer, nullable=True),
    Column("retired_reason", Text, nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

promotion_gate_runs = Table(
    "promotion_gate_runs",
    metadata,
    Column("run_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("idempotency_key", Text, nullable=False),
    Column("candidate_label", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("corpus_size", Integer, nullable=False),
    Column("task_class_count", Integer, nullable=False),
    Column("adversarial_count", Integer, nullable=False),
    Column("decision", Text, nullable=True),
    Column("gate_results", JSONB, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
    Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
)
