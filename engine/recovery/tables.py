"""SQLAlchemy Core table for `ExternalEffect` persistence (Chapter 3.3, 3.8's
`external_effects` -- see `schemas/objects/external_effect.json`'s
`x-dde-storage`).

`mission_id` is not named in Chapter 12.4's literal field list, but Chapter
3.2 mandates it for "every runtime/execution table" -- an `ExternalEffect`
is bound to a `WorkerRun` exactly as `CapabilityLease`/`CredentialHandle`
are, so this mirrors their own inclusion of it rather than treating 12.4's
sketch as an exhaustive column list.

`worker_run_id` is deliberately not foreign-keyed to `worker_runs`:
`prepare()`/`mark_sent()` each commit in their own unit of work BEFORE the
real side effect runs (a `PREPARED`/`SENT` row must survive a crash
mid-effect), while `WorkerManagerService.invoke_run` still holds the
`WorkerRun` insert uncommitted on a different connection. PostgreSQL READ
COMMITTED would reject the FK against that in-flight row -- the same
isolation reason `capability_leases.worker_run_id` is a soft reference
(see `engine.workers.service`'s DDE-017 module docstring).
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, Integer, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

external_effects = Table(
    "external_effects",
    metadata,
    Column("effect_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("worker_run_id", Uuid(as_uuid=True), nullable=False),
    Column("capability_lease_id", Uuid(as_uuid=True), nullable=False),
    Column("command_id", Uuid(as_uuid=True), nullable=False),
    Column("target_system", Text, nullable=False),
    Column("target_resource", Text, nullable=False),
    Column("operation", Text, nullable=False),
    Column("side_effect_class", Text, nullable=False),
    Column("idempotency_key", Text, nullable=False),
    Column("request_hash", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("external_reference", Text, nullable=True),
    Column("response_hash", Text, nullable=True),
    Column("reconciliation_method", Text, nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("confirmed_at", TIMESTAMP(timezone=True), nullable=True),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

checkpoints = Table(
    "checkpoints",
    metadata,
    Column("checkpoint_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("task_attempt_id", Uuid(as_uuid=True), nullable=False),
    Column("worker_run_id", Uuid(as_uuid=True), nullable=False),
    Column("context_package_id", Uuid(as_uuid=True), nullable=False),
    Column("execution_plan_id", Uuid(as_uuid=True), nullable=False),
    Column("completed_work", JSONB, nullable=False),
    Column("verified_work", JSONB, nullable=False),
    Column("pending_work", JSONB, nullable=False),
    Column("known_failures", JSONB, nullable=False),
    Column("next_action", Text, nullable=False),
    Column("do_not_repeat", JSONB, nullable=False),
    Column("artifact_refs", JSONB, nullable=False),
    Column("lease_refs", JSONB, nullable=False),
    Column("workspace_revision", Text, nullable=False),
    Column("integration_state", Text, nullable=False),
    Column("event_sequence", Integer, nullable=False),
    Column("integrity_hash", Text, nullable=False),
    Column("command_id", Uuid(as_uuid=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
