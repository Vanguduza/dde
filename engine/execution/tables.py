"""SQLAlchemy Core table for ExecutionPlan persistence (Chapter 3.3, 3.8).
Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated
from `schemas/objects/execution_plan.json` — the schema is authoritative
(Chapter 3.1); this module only maps the same columns onto SQLAlchemy Core
so `engine.execution` can read and write them inside a shared PostgreSQL
transaction (Chapter 3.5).

Chapter 3.8 lists ExecutionPlan's owner module as `execution`, created by
the Execution Planner; this module (and `engine.execution.repository`/
`engine.execution.service`) is that sole writer.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, Integer, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

execution_plans = Table(
    "execution_plans",
    metadata,
    Column("plan_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("route_decision_id", Uuid(as_uuid=True), nullable=False),
    Column("context_package_id", Uuid(as_uuid=True), nullable=False),
    Column("worker_profile_id", Text, nullable=False),
    Column("execution_environment_id", Uuid(as_uuid=True), nullable=False),
    Column("workspace_policy", JSONB, nullable=False),
    Column("capability_requirements", JSONB, nullable=False),
    Column("enforcement_tier", Text, nullable=False),
    Column("autonomy_level", Integer, nullable=False),
    Column("resource_budget", JSONB, nullable=False),
    Column("time_budget", JSONB, nullable=False),
    Column("token_budget", JSONB, nullable=False),
    Column("network_policy", JSONB, nullable=False),
    Column("filesystem_policy", JSONB, nullable=False),
    Column("verification_plan_id", Uuid(as_uuid=True), nullable=True),
    Column("acceptance_oracle_id", Uuid(as_uuid=True), nullable=True),
    Column("write_scope_lease_id", Uuid(as_uuid=True), nullable=True),
    Column("checkpoint_policy", JSONB, nullable=False),
    Column("retry_policy", JSONB, nullable=False),
    Column("escalation_policy", JSONB, nullable=False),
    Column("plan_hash", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("approved_at", TIMESTAMP(timezone=True), nullable=True),
    Column("started_at", TIMESTAMP(timezone=True), nullable=True),
    Column("ended_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
