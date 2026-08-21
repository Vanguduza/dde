"""SQLAlchemy Core tables for the Chapter 5.10 knowledge graph (DDE-033).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, generated from
`schemas/objects/asserted_edge.json` and `schemas/objects/derived_edge.json`
-- the schema is authoritative (Chapter 3.1); this module only maps the
same columns onto SQLAlchemy Core so `engine.knowledge` can read and write
them inside a shared PostgreSQL transaction (Chapter 3.5).
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Column, MetaData, Table, Text, Uuid

metadata = MetaData()

asserted_edges = Table(
    "asserted_edges",
    metadata,
    Column("edge_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("edge_type", Text, nullable=False),
    Column("source_key", Text, nullable=False),
    Column("target_key", Text, nullable=False),
    Column("asserted_by_principal", Uuid(as_uuid=True), nullable=True),
    Column("asserted_by_mechanism", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("retracted_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

derived_edges = Table(
    "derived_edges",
    metadata,
    Column("derived_edge_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("edge_type", Text, nullable=False),
    Column("source_key", Text, nullable=False),
    Column("target_key", Text, nullable=False),
    Column("derived_at", TIMESTAMP(timezone=True), nullable=False),
    Column("derived_from_commit", Text, nullable=False),
    Column("deriver_version", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
