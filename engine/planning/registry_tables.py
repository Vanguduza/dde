"""SQLAlchemy Core tables for the Chapter 4.3 planning registries
(migration 0014).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated
from `schemas/objects/{mission_template,plan_draft}.json` -- the schema
is authoritative (Chapter 3.1); this module only maps the same columns
onto SQLAlchemy Core. Ownership per Chapter 3.8: the planner owns
decomposition, and both objects are decomposition artifacts -- a
template is what deterministic planning instantiates, a draft is what
model-assisted planning proposes.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

mission_templates = Table(
    "mission_templates",
    metadata,
    Column("template_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("template_key", Text, nullable=False),
    Column("template_version", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("nodes", JSONB, nullable=False),
    Column("edges", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("planner_policy_version", Text, nullable=False),
    Column("created_by", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

plan_drafts = Table(
    "plan_drafts",
    metadata,
    Column("draft_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("origin", Text, nullable=False),
    Column("adapter_ref", Text, nullable=True),
    Column("origin_policy_version", Text, nullable=False),
    Column("nodes", JSONB, nullable=False),
    Column("edges", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("refusals", JSONB, nullable=False),
    Column("promoted_graph_id", Uuid(as_uuid=True), nullable=True),
    Column("provenance_key", Text, nullable=False),
    Column("created_by_principal", Uuid(as_uuid=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
