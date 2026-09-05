"""SQLAlchemy Core mappings for DDE-069 M8 source intelligence.

The authoritative column contract lives in schemas/objects. This module gives
Source Intelligence one shared transaction surface over those generated tables.
"""

from __future__ import annotations

from sqlalchemy import (
    TIMESTAMP,
    Column,
    Index,
    Integer,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

from engine.studio.tables import metadata

design_sources = Table(
    "design_sources",
    metadata,
    Column("source_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("provider_key", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("source_class", Text, nullable=False),
    Column("adapter_kind", Text, nullable=False),
    Column("priority", Integer, nullable=False),
    Column("status", Text, nullable=False),
    Column("health_detail", Text, nullable=True),
    Column("capabilities", JSONB, nullable=False),
    Column("config", JSONB, nullable=False),
    Column("item_count", Integer, nullable=True),
    Column("last_checked_at", TIMESTAMP(timezone=True), nullable=True),
    Column("lock_version", Integer, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
    UniqueConstraint("project_id", "provider_key"),
)
Index(
    "ix_design_sources_project_priority",
    design_sources.c.project_id,
    design_sources.c.priority,
)


design_source_search_runs = Table(
    "design_source_search_runs",
    metadata,
    Column("search_run_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=True),
    Column("query", Text, nullable=False),
    Column("provider_keys", JSONB, nullable=False),
    Column("requested_capabilities", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("result_count", Integer, nullable=False),
    Column("degradation", JSONB, nullable=False),
    Column("started_at", TIMESTAMP(timezone=True), nullable=False),
    Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
Index(
    "ix_design_source_search_project_started",
    design_source_search_runs.c.project_id,
    design_source_search_runs.c.started_at,
)


design_source_artifacts = Table(
    "design_source_artifacts",
    metadata,
    Column("artifact_id", Uuid(as_uuid=True), primary_key=True),
    Column("source_id", Uuid(as_uuid=True), nullable=False),
    Column("search_run_id", Uuid(as_uuid=True), nullable=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("provider_artifact_key", Text, nullable=False),
    Column("artifact_kind", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("source_uri", Text, nullable=True),
    Column("version_ref", Text, nullable=True),
    Column("content_hash", Text, nullable=True),
    Column("content_object_ref", Text, nullable=True),
    Column("content_object_backend", Text, nullable=True),
    Column("content_size_bytes", Integer, nullable=True),
    Column("framework", Text, nullable=True),
    Column("supported_archetypes", JSONB, nullable=False),
    Column("dependency_manifest", JSONB, nullable=False),
    Column("license_state", Text, nullable=False),
    Column("license_ids", JSONB, nullable=False),
    Column("security_state", Text, nullable=False),
    Column("accessibility_state", Text, nullable=False),
    Column("compatibility_state", Text, nullable=False),
    Column("retrieval_state", Text, nullable=False),
    Column("metadata", JSONB, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
    UniqueConstraint("source_id", "provider_artifact_key"),
)
Index(
    "ix_design_source_artifacts_project_source",
    design_source_artifacts.c.project_id,
    design_source_artifacts.c.source_id,
)
Index(
    "ix_design_source_artifacts_project_state",
    design_source_artifacts.c.project_id,
    design_source_artifacts.c.retrieval_state,
)


design_source_admissions = Table(
    "design_source_admissions",
    metadata,
    Column("admission_id", Uuid(as_uuid=True), primary_key=True),
    Column("artifact_id", Uuid(as_uuid=True), nullable=False),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("compiler_version", Text, nullable=False),
    Column("framework_state", Text, nullable=False),
    Column("license_state", Text, nullable=False),
    Column("dependency_state", Text, nullable=False),
    Column("security_state", Text, nullable=False),
    Column("accessibility_state", Text, nullable=False),
    Column("design_system_state", Text, nullable=False),
    Column("token_mapping_report", JSONB, nullable=False),
    Column("unsupported_behaviors", JSONB, nullable=False),
    Column("hard_failures", JSONB, nullable=False),
    Column("validation_obligations", JSONB, nullable=False),
    Column("state", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
    UniqueConstraint("artifact_id", "content_hash", "compiler_version"),
)
Index(
    "ix_design_source_admission_project_state",
    design_source_admissions.c.project_id,
    design_source_admissions.c.state,
)


frontend_provenance_records = Table(
    "frontend_provenance_records",
    metadata,
    Column("provenance_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("subject_kind", Text, nullable=False),
    Column("subject_ref", Text, nullable=False),
    Column("source_id", Uuid(as_uuid=True), nullable=True),
    Column("artifact_id", Uuid(as_uuid=True), nullable=True),
    Column("admission_id", Uuid(as_uuid=True), nullable=True),
    Column("usage_kind", Text, nullable=False),
    Column("attribution_weight", Numeric, nullable=True),
    Column("source_revision", Text, nullable=True),
    Column("license_state", Text, nullable=False),
    Column("security_state", Text, nullable=False),
    Column("decision_ref", Text, nullable=True),
    Column("metadata", JSONB, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
Index(
    "ix_frontend_provenance_subject",
    frontend_provenance_records.c.project_id,
    frontend_provenance_records.c.subject_kind,
    frontend_provenance_records.c.subject_ref,
)


frontend_templates = Table(
    "frontend_templates",
    metadata,
    Column("template_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("source_artifact_id", Uuid(as_uuid=True), nullable=True),
    Column("title", Text, nullable=False),
    Column("source_refs", JSONB, nullable=False),
    Column("supported_archetypes", JSONB, nullable=False),
    Column("expected_screen_coverage", Numeric, nullable=True),
    Column("score_summary", JSONB, nullable=False),
    Column("hard_failures", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("content_hash", Text, nullable=True),
    Column("content_object_ref", Text, nullable=True),
    Column("content_object_backend", Text, nullable=True),
    Column("content_size_bytes", Integer, nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
Index(
    "ix_frontend_templates_project_status",
    frontend_templates.c.project_id,
    frontend_templates.c.status,
)


frontend_candidate_scores = Table(
    "frontend_candidate_scores",
    metadata,
    Column("score_id", Uuid(as_uuid=True), primary_key=True),
    Column("candidate_id", Uuid(as_uuid=True), nullable=False),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("verification_run_id", Uuid(as_uuid=True), nullable=True),
    Column("score_state", Text, nullable=False),
    Column("overall_score", Numeric, nullable=True),
    Column("classification", Text, nullable=False),
    Column("dimensions", JSONB, nullable=False),
    Column("hard_failures", JSONB, nullable=False),
    Column("evidence_refs", JSONB, nullable=False),
    Column("computed_at", TIMESTAMP(timezone=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
    UniqueConstraint("candidate_id", "sequence"),
)
Index(
    "ix_frontend_candidate_scores_candidate",
    frontend_candidate_scores.c.candidate_id,
    frontend_candidate_scores.c.sequence,
)

frontend_source_blend_preferences = Table(
    "frontend_source_blend_preferences",
    metadata,
    Column("preference_id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("mission_id", Uuid(as_uuid=True), nullable=True),
    Column("scope_key", Text, nullable=False),
    Column("weights", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("created_by", Uuid(as_uuid=True), nullable=True),
    Column("supersedes_id", Uuid(as_uuid=True), nullable=True),
    Column("lock_version", Integer, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
)
Index(
    "ix_frontend_source_blend_project_scope",
    frontend_source_blend_preferences.c.project_id,
    frontend_source_blend_preferences.c.scope_key,
    frontend_source_blend_preferences.c.status,
)
