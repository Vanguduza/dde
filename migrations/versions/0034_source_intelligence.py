"""DDE-069 M8 Source Intelligence persistence."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def _rls(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            "USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) "
            "AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) "
            "WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) "
            "AS uuid) "
            "AND project_id = CAST(current_setting('dde.project_id', true) AS uuid))"
        )
    )


def _scope_fks() -> tuple[sa.ForeignKeyConstraint, sa.ForeignKeyConstraint]:
    return (
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
    )


def upgrade() -> None:
    op.create_table(
        "design_sources",
        sa.Column("source_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("source_class", sa.Text(), nullable=False),
        sa.Column("adapter_kind", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("health_detail", sa.Text(), nullable=True),
        sa.Column("capabilities", postgresql.JSONB(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=True),
        sa.Column("last_checked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("priority >= 0"),
        sa.CheckConstraint("lock_version >= 1"),
        sa.UniqueConstraint("project_id", "provider_key"),
        *_scope_fks(),
    )
    op.create_index(
        "ix_design_sources_project_priority",
        "design_sources",
        ["project_id", "priority"],
    )
    op.create_table(
        "design_source_search_runs",
        sa.Column("search_run_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("provider_keys", postgresql.JSONB(), nullable=False),
        sa.Column("requested_capabilities", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("degradation", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("result_count >= 0"),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.mission_id"]),
        *_scope_fks(),
    )
    op.create_index(
        "ix_design_source_search_project_started",
        "design_source_search_runs",
        ["project_id", "started_at"],
    )
    op.create_table(
        "design_source_artifacts",
        sa.Column("artifact_id", sa.Uuid(), primary_key=True),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("search_run_id", sa.Uuid(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("provider_artifact_key", sa.Text(), nullable=False),
        sa.Column("artifact_kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("version_ref", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("content_object_ref", sa.Text(), nullable=True),
        sa.Column("content_object_backend", sa.Text(), nullable=True),
        sa.Column("content_size_bytes", sa.Integer(), nullable=True),
        sa.Column("framework", sa.Text(), nullable=True),
        sa.Column("supported_archetypes", postgresql.JSONB(), nullable=False),
        sa.Column("dependency_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("license_state", sa.Text(), nullable=False),
        sa.Column("license_ids", postgresql.JSONB(), nullable=False),
        sa.Column("security_state", sa.Text(), nullable=False),
        sa.Column("accessibility_state", sa.Text(), nullable=False),
        sa.Column("compatibility_state", sa.Text(), nullable=False),
        sa.Column("retrieval_state", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "provider_artifact_key"),
        sa.ForeignKeyConstraint(["source_id"], ["design_sources.source_id"]),
        sa.ForeignKeyConstraint(
            ["search_run_id"], ["design_source_search_runs.search_run_id"]
        ),
        *_scope_fks(),
    )
    op.create_index(
        "ix_design_source_artifacts_project_source",
        "design_source_artifacts",
        ["project_id", "source_id"],
    )
    op.create_index(
        "ix_design_source_artifacts_project_state",
        "design_source_artifacts",
        ["project_id", "retrieval_state"],
    )
    op.create_table(
        "design_source_admissions",
        sa.Column("admission_id", sa.Uuid(), primary_key=True),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("compiler_version", sa.Text(), nullable=False),
        sa.Column("framework_state", sa.Text(), nullable=False),
        sa.Column("license_state", sa.Text(), nullable=False),
        sa.Column("dependency_state", sa.Text(), nullable=False),
        sa.Column("security_state", sa.Text(), nullable=False),
        sa.Column("accessibility_state", sa.Text(), nullable=False),
        sa.Column("design_system_state", sa.Text(), nullable=False),
        sa.Column("token_mapping_report", postgresql.JSONB(), nullable=False),
        sa.Column("unsupported_behaviors", postgresql.JSONB(), nullable=False),
        sa.Column("hard_failures", postgresql.JSONB(), nullable=False),
        sa.Column("validation_obligations", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint("artifact_id", "content_hash", "compiler_version"),
        sa.ForeignKeyConstraint(
            ["artifact_id"], ["design_source_artifacts.artifact_id"]
        ),
        *_scope_fks(),
    )
    op.create_index(
        "ix_design_source_admission_project_state",
        "design_source_admissions",
        ["project_id", "state"],
    )
    op.create_table(
        "frontend_provenance_records",
        sa.Column("provenance_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("subject_kind", sa.Text(), nullable=False),
        sa.Column("subject_ref", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("admission_id", sa.Uuid(), nullable=True),
        sa.Column("usage_kind", sa.Text(), nullable=False),
        sa.Column("attribution_weight", sa.Numeric(), nullable=True),
        sa.Column("source_revision", sa.Text(), nullable=True),
        sa.Column("license_state", sa.Text(), nullable=False),
        sa.Column("security_state", sa.Text(), nullable=False),
        sa.Column("decision_ref", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attribution_weight IS NULL OR "
            "(attribution_weight >= 0 AND attribution_weight <= 1)"
        ),
        sa.ForeignKeyConstraint(["source_id"], ["design_sources.source_id"]),
        sa.ForeignKeyConstraint(
            ["artifact_id"], ["design_source_artifacts.artifact_id"]
        ),
        sa.ForeignKeyConstraint(
            ["admission_id"], ["design_source_admissions.admission_id"]
        ),
        *_scope_fks(),
    )
    op.create_index(
        "ix_frontend_provenance_subject",
        "frontend_provenance_records",
        ["project_id", "subject_kind", "subject_ref"],
    )
    op.create_table(
        "frontend_templates",
        sa.Column("template_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_refs", postgresql.JSONB(), nullable=False),
        sa.Column("supported_archetypes", postgresql.JSONB(), nullable=False),
        sa.Column("expected_screen_coverage", sa.Numeric(), nullable=True),
        sa.Column("score_summary", postgresql.JSONB(), nullable=False),
        sa.Column("hard_failures", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("content_object_ref", sa.Text(), nullable=True),
        sa.Column("content_object_backend", sa.Text(), nullable=True),
        sa.Column("content_size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            "expected_screen_coverage IS NULL OR "
            "(expected_screen_coverage >= 0 AND expected_screen_coverage <= 1)"
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"], ["design_source_artifacts.artifact_id"]
        ),
        *_scope_fks(),
    )
    op.create_index(
        "ix_frontend_templates_project_status",
        "frontend_templates",
        ["project_id", "status"],
    )
    op.create_table(
        "frontend_candidate_scores",
        sa.Column("score_id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("verification_run_id", sa.Uuid(), nullable=True),
        sa.Column("score_state", sa.Text(), nullable=False),
        sa.Column("overall_score", sa.Numeric(), nullable=True),
        sa.Column("classification", sa.Text(), nullable=False),
        sa.Column("dimensions", postgresql.JSONB(), nullable=False),
        sa.Column("hard_failures", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=False),
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("sequence >= 1"),
        sa.CheckConstraint(
            "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 100)"
        ),
        sa.UniqueConstraint("candidate_id", "sequence"),
        sa.ForeignKeyConstraint(["candidate_id"], ["frontend_candidates.candidate_id"]),
        sa.ForeignKeyConstraint(
            ["verification_run_id"], ["verification_runs.verification_run_id"]
        ),
        *_scope_fks(),
    )
    op.create_index(
        "ix_frontend_candidate_scores_candidate",
        "frontend_candidate_scores",
        ["candidate_id", "sequence"],
    )
    op.create_table(
        "frontend_source_blend_preferences",
        sa.Column("preference_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=True),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.Column("weights", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("lock_version >= 1"),
        sa.CheckConstraint("status IN ('ACTIVE','SUPERSEDED')"),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.mission_id"]),
        sa.ForeignKeyConstraint(["created_by"], ["principals.principal_id"]),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["frontend_source_blend_preferences.preference_id"]
        ),
        *_scope_fks(),
    )
    op.create_index(
        "ix_frontend_source_blend_project_scope",
        "frontend_source_blend_preferences",
        ["project_id", "scope_key", "status"],
    )
    op.create_index(
        "uq_frontend_source_blend_active_scope",
        "frontend_source_blend_preferences",
        ["project_id", "scope_key"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    for table in (
        "design_sources",
        "design_source_search_runs",
        "design_source_artifacts",
        "design_source_admissions",
        "frontend_provenance_records",
        "frontend_templates",
        "frontend_candidate_scores",
        "frontend_source_blend_preferences",
    ):
        _rls(table)


def downgrade() -> None:
    for table in (
        "frontend_source_blend_preferences",
        "frontend_candidate_scores",
        "frontend_templates",
        "frontend_provenance_records",
        "design_source_admissions",
        "design_source_artifacts",
        "design_source_search_runs",
        "design_sources",
    ):
        op.drop_table(table)
