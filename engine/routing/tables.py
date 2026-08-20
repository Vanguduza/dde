"""SQLAlchemy Core table for RouteDecision persistence (Chapter 3.3, 3.8).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated
from `schemas/objects/route_decision.json` — the schema is authoritative
(Chapter 3.1); this module only maps the same columns onto SQLAlchemy Core
so `engine.routing` can read and write them inside a shared PostgreSQL
transaction (Chapter 3.5).

Chapter 3.8's object ownership matrix lists RouteDecision's owner module as
`routing`; this module (and `engine.routing.repository`/
`engine.routing.service`) is that sole writer.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, MetaData, Numeric, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

route_decisions = Table(
    "route_decisions",
    metadata,
    Column("decision_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("candidates", JSONB, nullable=False),
    Column("selected_worker_profile_id", Text, nullable=False),
    Column("workload_class", Text, nullable=False),
    Column("required_capabilities", JSONB, nullable=False),
    Column("required_environment_class", Text, nullable=False),
    Column("reason_codes", JSONB, nullable=False),
    Column("predicted_success", Numeric, nullable=True),
    Column("predicted_cost", Numeric, nullable=True),
    Column("predicted_latency", Numeric, nullable=True),
    Column("confidence", Numeric, nullable=True),
    Column("selection_source", Text, nullable=False),
    Column("selection_propensity", Numeric, nullable=False),
    Column("fallback_plan", JSONB, nullable=False),
    Column("escalation_plan", JSONB, nullable=False),
    Column("policy_version", Text, nullable=False),
    Column("decision_hash", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
