"""Donor Lab persistence (Chapter 13.8 / DDE-046).

Hand-written SQLAlchemy Core mirror of
`schemas/objects/{donor_artifact,feature_dna}.json` plus migration 0017.
"""

from __future__ import annotations

from sqlalchemy import (
    TIMESTAMP,
    Column,
    Integer,
    MetaData,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

donor_artifacts = Table(
    "donor_artifacts",
    metadata,
    Column("donor_artifact_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=True),
    Column("source_uri", Text, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("source_class", Text, nullable=False),
    Column("authority_rank", Integer, nullable=False),
    Column("media_kind", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("provenance", JSONB, nullable=False),
    Column("feature_dna_id", Uuid(as_uuid=True), nullable=True),
    Column("injection_findings", JSONB, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)

feature_dna = Table(
    "feature_dna",
    metadata,
    Column("feature_dna_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("donor_artifact_id", Uuid(as_uuid=True), nullable=False),
    Column("title", Text, nullable=False),
    Column("body", JSONB, nullable=False),
    Column("donor_sources", JSONB, nullable=False),
    Column("dna_hash", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
