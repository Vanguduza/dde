"""SQLAlchemy Core table mappings for Chapter 16.4 overhead instrumentation.

Hand-written to mirror the canonical DDL emitted from
`schemas/sql/0001_stage1.sql` (Chapter 3.1 SSOT discipline).
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
    UniqueConstraint,
    Uuid,
)

metadata = MetaData()


control_plane_overhead_tasks = Table(
    "control_plane_overhead_tasks",
    metadata,
    Column("overhead_task_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("task_attempt_id", Uuid(as_uuid=True), nullable=False),
    Column("worker_run_id", Uuid(as_uuid=True), nullable=False),
    Column("execution_plan_id", Uuid(as_uuid=True), nullable=False),
    Column("context_package_id", Uuid(as_uuid=True), nullable=False),
    Column("environment_id", Uuid(as_uuid=True), nullable=False),
    Column("estimated_effort", Text, nullable=False),
    Column("context_assembly_tokens", Integer, nullable=False),
    Column("context_critic_tokens", Integer, nullable=False),
    Column("routing_tokens", Integer, nullable=False),
    Column("route_critic_tokens", Integer, nullable=False),
    Column("planning_tokens", Integer, nullable=False),
    Column("judge_tokens", Integer, nullable=False),
    Column("overhead_tokens", Integer, nullable=False),
    Column("environment_provisioning_ms", Integer, nullable=False),
    Column("queue_wait_seconds", Numeric, nullable=False),
    Column(
        "overhead_seconds_before_first_worker_action_seconds", Numeric, nullable=False
    ),
    Column("context_critic_invoked", Boolean, nullable=False),
    Column("route_critic_invoked", Boolean, nullable=False),
    Column("workload_class", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
    UniqueConstraint("worker_run_id"),
)


tenant_overhead_budget_settings = Table(
    "tenant_overhead_budget_settings",
    metadata,
    Column("tenant_id", Uuid(as_uuid=True), primary_key=True),
    Column("hard_cap_overhead_token_share", Numeric, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)


workload_class_cost_metrics = Table(
    "workload_class_cost_metrics",
    metadata,
    Column("metric_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("workload_class", Text, nullable=False),
    Column("verified_success_count", Integer, nullable=False),
    Column("total_overhead_tokens", Integer, nullable=False),
    Column("cost_tokens_per_verified_success", Numeric, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
    UniqueConstraint("tenant_id", "project_id", "workload_class"),
)
