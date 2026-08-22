"""SQLAlchemy Core table for the Chapter 6.4 Routing Simulation Model
fixture generator (DDE-036).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, generated from
`schemas/objects/routing_simulation_run.json` -- the schema is
authoritative (Chapter 3.1); this module only maps the same columns onto
SQLAlchemy Core so `engine.simulation` can read and write them inside a
shared PostgreSQL transaction (Chapter 3.5).
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Boolean, Column, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

routing_simulation_runs = Table(
    "routing_simulation_runs",
    metadata,
    Column("run_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("seed", Text, nullable=False),
    Column("policy_version", Text, nullable=False),
    Column("model_version", Text, nullable=False),
    Column("scenario_classes", JSONB, nullable=False, server_default="[]"),
    Column("scenario_results", JSONB, nullable=False, server_default="[]"),
    Column("experience_origin", Text, nullable=False),
    Column("excluded_from_routing_learning", Boolean, nullable=False),
    Column("disclosed_gaps", JSONB, nullable=False, server_default="[]"),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
