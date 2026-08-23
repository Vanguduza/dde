"""SQLAlchemy Core tables for the Chapter 11.5 invariant engine
(migration 0013).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated
from `schemas/objects/{domain_invariant,invariant_evaluation}.json` -- the
schema is authoritative (Chapter 3.1); this module only maps the same
columns onto SQLAlchemy Core. Ownership per Chapter 3.6/3.8: verification
owns "oracle, runners, product envs" — invariants are the datastore-check
arm of that same verification domain, so this module tree lives under
`engine.invariants` as its cohesive unit.
"""

from __future__ import annotations

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    Integer,
    MetaData,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

domain_invariants = Table(
    "domain_invariants",
    metadata,
    Column("invariant_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=True),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("predicate", JSONB, nullable=False),
    Column("financial_state", Boolean, nullable=False),
    Column("required_fixture_class", Text, nullable=False),
    Column("product_env_class", Text, nullable=False),
    Column("definition_version", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("created_by", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

invariant_evaluations = Table(
    "invariant_evaluations",
    metadata,
    Column("evaluation_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=True),
    Column("invariant_id", Uuid(as_uuid=True), nullable=False),
    Column("definition_version", Text, nullable=False),
    Column("product_env_id", Uuid(as_uuid=True), nullable=False),
    Column("datastore_ref", Text, nullable=True),
    Column("sequence", Integer, nullable=False),
    Column("status", Text, nullable=False),
    Column("violations", JSONB, nullable=False),
    Column("rows_checked", Integer, nullable=False),
    Column("financial_state", Boolean, nullable=False),
    Column("repair_task_ref", Text, nullable=True),
    Column("seed_dataset_id", Uuid(as_uuid=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
