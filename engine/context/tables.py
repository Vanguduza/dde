"""SQLAlchemy Core table for ContextPackage persistence (Chapter 3.3, 3.8).

Hand-written to mirror `schemas/sql/0001_stage1.sql`, which is generated
from `schemas/objects/context_package.json` — the schema is authoritative
(Chapter 3.1); this module only maps the same columns onto SQLAlchemy
Core so `engine.context` can read and write them inside a shared
PostgreSQL transaction (Chapter 3.5).

Chapter 3.8's object ownership matrix lists `ContextPackage`'s owner
module as `context`; this module (and `engine.context.repository`/
`engine.context.service`) is that sole writer.
"""

from __future__ import annotations

from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, MetaData, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

context_packages = Table(
    "context_packages",
    metadata,
    Column("package_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True), nullable=False),
    Column("version", Integer, nullable=False),
    Column("assembly_hash", Text, nullable=False),
    Column("index_version", Text, nullable=False),
    Column("index_lag_commits", Integer, nullable=False),
    Column("coverage", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("retrievers_used", JSONB, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

context_indexes = Table(
    "context_indexes",
    metadata,
    Column("index_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("current_version", Text, nullable=False),
    Column("embedding_model_version", Text, nullable=False),
    Column("head_commit_sha", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

context_chunks = Table(
    "context_chunks",
    metadata,
    Column("chunk_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("index_version", Text, nullable=False),
    Column("embedding_model_version", Text, nullable=False),
    Column("file_path", Text, nullable=False),
    Column("symbol_path", Text, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("start_line", Integer, nullable=False),
    Column("end_line", Integer, nullable=False),
    Column("language", Text, nullable=False),
    Column("commit_sha", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("embedding", JSONB, nullable=False),
    Column("current", Boolean, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
