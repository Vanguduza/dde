"""SQLAlchemy Core tables for static-secret capture (Chapter 14.3).

`captured_provider_credentials` mirrors schemas/objects metadata.
`broker_static_secret_material` is broker-private (AGENTS.md).
At-rest encryption deferred on StaticSecretCaptureService.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, MetaData, Table, Text, Uuid

metadata = MetaData()

captured_provider_credentials = Table(
    "captured_provider_credentials",
    metadata,
    Column("capture_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("provider_id", Text, nullable=False),
    Column("domain", Text, nullable=True),
    Column("secret_hash", Text, nullable=False),
    Column("fingerprint", Text, nullable=False),
    Column("last4", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("supersedes_capture_id", Uuid(as_uuid=True), nullable=True),
    Column("superseded_by_capture_id", Uuid(as_uuid=True), nullable=True),
    Column("captured_by", Text, nullable=False),
    Column("captured_at", TIMESTAMP(timezone=True), nullable=False),
    Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

broker_static_secret_material = Table(
    "broker_static_secret_material",
    metadata,
    Column("capture_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("provider_id", Text, nullable=False),
    Column("secret_value", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
)
