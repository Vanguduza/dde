"""SQLAlchemy Core tables for the gateway session surface (Chapter 15.1).

`client_sessions` is written by `engine.gateway.sessions`. `principals` and
`principal_grants` are read-only here: they are written by the tenancy
authority layer (DDE-051), and the gateway only resolves identity from them
(Chapter 13.9: tenant identity derives from the authenticated principal,
never from a client-supplied target id).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, generated from
`schemas/objects/{client_session,principal,principal_grant}.json`.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

client_sessions = Table(
    "client_sessions",
    metadata,
    Column("session_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("principal_id", Uuid(as_uuid=True), nullable=False),
    Column("client_type", Text, nullable=False),
    Column("device_id", Uuid(as_uuid=True), nullable=True),
    Column("protocol_version", Text, nullable=False),
    Column("scopes", JSONB, nullable=False),
    Column("connected_at", TIMESTAMP(timezone=True), nullable=False),
    Column("last_seen_at", TIMESTAMP(timezone=True), nullable=False),
    Column("subscriptions", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

principals = Table(
    "principals",
    metadata,
    Column("principal_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("slug", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

principal_grants = Table(
    "principal_grants",
    metadata,
    Column("grant_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=True),
    Column("principal_id", Uuid(as_uuid=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
