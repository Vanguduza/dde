"""SQLAlchemy Core table for `CapabilityLease` persistence (Chapter 3.3, 3.8's
`capability_leases` -- see `schemas/objects/capability_lease.json`'s
`x-dde-storage`).

A new file, not an addition to `engine.capabilities.tables` -- the mission
brief that built that module (DDE-016) is frozen except for read calls from
this lease service; this table gets its own module instead, exactly the way
`engine.integration.tables` holds both `write_scope_leases` and
`integration_proposals` as siblings rather than forcing every lease-shaped
table through one file.

`worker_run_id`/`environment_id` are deliberately not foreign-keyed to
`worker_runs`/`execution_environments`: Chapter 9.2 lists them as lease
identity fields, but nothing in Chapter 3.9's creation order requires a
`WorkerRun`/`ExecutionEnvironment` row to keep existing for as long as an
already-granted lease's audit trail does (a replaced run must not orphan the
lease history that explains what it was authorised to do). A soft reference
is a real, flagged interpretation, not an omission.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Boolean, Column, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

capability_leases = Table(
    "capability_leases",
    metadata,
    Column("lease_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("execution_plan_id", Uuid(as_uuid=True), nullable=False),
    Column("worker_run_id", Uuid(as_uuid=True), nullable=True),
    Column("environment_id", Uuid(as_uuid=True), nullable=True),
    Column("capability_id", Text, nullable=False),
    Column("capability_version", Text, nullable=False),
    Column("resource_scope", JSONB, nullable=False),
    Column("operation_scope", Text, nullable=False),
    Column("constraints", JSONB, nullable=False),
    Column("issued_by_policy_version", Text, nullable=False),
    Column("issued_at", TIMESTAMP(timezone=True), nullable=False),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
    Column("revocable", Boolean, nullable=False),
    Column("status", Text, nullable=False),
    Column("denied_reason", Text, nullable=True),
    Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
    Column("revocation_reason", Text, nullable=True),
    Column("lease_hash", Text, nullable=False),
    Column("requested_by", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
