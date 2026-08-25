"""`organizations` table mapping for the tenancy authority (Chapter 13.9).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, generated from
`schemas/objects/organization.json` -- the schema is authoritative
(Chapter 3.1); this module only maps the same columns onto SQLAlchemy Core
so the gateway can read organization membership inside a shared
transaction.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, MetaData, Table, Text, Uuid

metadata = MetaData()

organizations = Table(
    "organizations",
    metadata,
    Column("organization_id", Uuid(as_uuid=True), primary_key=True),
    Column("slug", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
