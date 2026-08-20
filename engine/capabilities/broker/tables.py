"""SQLAlchemy Core table for `CredentialHandle` persistence (Chapter 3.3,
3.8's `credential_handles` -- see `schemas/objects/credential_handle.json`'s
`x-dde-storage`).

A new file under `engine/capabilities/broker/`, not `engine.capabilities.
lease_tables` -- Chapter 3.8 gives "Credential handle" its own owner module
(`capabilities/broker`), distinct from `CapabilityLease`'s (`capabilities`).
`secret_hash` is the only credential-shaped column: a SHA-256 digest, never
the raw value (see `schemas/objects/credential_handle.json`'s description
and `engine.capabilities.broker.service`'s module docstring for the design
choice this implements).
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

credential_handles = Table(
    "credential_handles",
    metadata,
    Column("handle_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("worker_run_id", Uuid(as_uuid=True), nullable=True),
    Column("lease_id", Uuid(as_uuid=True), nullable=False),
    Column("capability_id", Text, nullable=False),
    Column("provider_id", Text, nullable=False),
    Column("provider_ref", Text, nullable=True),
    Column("resource_scope", JSONB, nullable=False),
    Column("issued_by_policy_version", Text, nullable=False),
    Column("secret_hash", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("issued_at", TIMESTAMP(timezone=True), nullable=False),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
    Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
    Column("revocation_reason", Text, nullable=True),
    Column("supersedes_handle_id", Uuid(as_uuid=True), nullable=True),
    Column("superseded_by_handle_id", Uuid(as_uuid=True), nullable=True),
    Column("requested_by", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
