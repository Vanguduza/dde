# ruff: noqa: E501
"""Domain-neutral Source Intelligence and automation corpus persistence.

Revision ID: 0040
Revises: 0039
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None

_NEW_TABLES = (
    "source_records",
    "source_artifacts",
    "source_admissions",
    "automation_corpus_snapshots",
    "automation_workflow_artifacts",
    "automation_pattern_descriptors",
)


def _scope_columns() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
    )


def _add_scope_fks(table: str) -> None:
    op.create_foreign_key(
        f"{table}_tenant_fkey", table, "tenants", ["tenant_id"], ["tenant_id"]
    )
    op.create_foreign_key(
        f"{table}_project_fkey", table, "projects", ["project_id"], ["project_id"]
    )


def _enable_rls(table: str) -> None:
    predicate = (
        "tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) "
        "AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)"
    )
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON {table} "
        f"USING ({predicate}) WITH CHECK ({predicate})"
    )


def _create_source_tables() -> None:
    tenant, project = _scope_columns()
    op.create_table(
        "source_records",
        sa.Column("source_id", sa.Uuid(), primary_key=True),
        tenant,
        project,
        sa.Column("provider_key", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("source_domain", sa.Text(), nullable=False),
        sa.Column("source_class", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_trust", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("policy_revision", sa.Text(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "provider_key"),
    )
    _add_scope_fks("source_records")

    tenant, project = _scope_columns()
    op.create_table(
        "source_artifacts",
        sa.Column("artifact_id", sa.Uuid(), primary_key=True),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        tenant,
        project,
        sa.Column("parent_artifact_id", sa.Uuid()),
        sa.Column("artifact_kind", sa.Text(), nullable=False),
        sa.Column("provider_artifact_key", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_uri", sa.Text()),
        sa.Column("revision", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("content_object_ref", sa.Text()),
        sa.Column("content_object_backend", sa.Text()),
        sa.Column("content_size_bytes", sa.Integer()),
        sa.Column("media_type", sa.Text()),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "provenance",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source_id", "provider_artifact_key", "revision", "content_hash"
        ),
    )
    _add_scope_fks("source_artifacts")
    op.create_foreign_key(
        "source_artifacts_source_fkey",
        "source_artifacts",
        "source_records",
        ["source_id"],
        ["source_id"],
    )
    op.create_foreign_key(
        "source_artifacts_parent_fkey",
        "source_artifacts",
        "source_artifacts",
        ["parent_artifact_id"],
        ["artifact_id"],
    )

    tenant, project = _scope_columns()
    op.create_table(
        "source_admissions",
        sa.Column("admission_id", sa.Uuid(), primary_key=True),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        tenant,
        project,
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("compiler_version", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("qualification_domain", sa.Text(), nullable=False),
        sa.Column("qualification_profile", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("source_trust", sa.Text(), nullable=False),
        sa.Column("reuse_class", sa.Text(), nullable=False),
        sa.Column(
            "analysis",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "hard_failures",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "validation_obligations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "provenance",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("security_state", sa.Text(), nullable=False),
        sa.Column("license_state", sa.Text(), nullable=False),
        sa.Column("provenance_state", sa.Text(), nullable=False),
        sa.Column("sanitization_state", sa.Text(), nullable=False),
        sa.Column("injection_state", sa.Text(), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "artifact_id", "content_hash", "compiler_version", "policy_version"
        ),
    )
    _add_scope_fks("source_admissions")
    op.create_foreign_key(
        "source_admissions_source_fkey",
        "source_admissions",
        "source_records",
        ["source_id"],
        ["source_id"],
    )
    op.create_foreign_key(
        "source_admissions_artifact_fkey",
        "source_admissions",
        "source_artifacts",
        ["artifact_id"],
        ["artifact_id"],
    )


def _create_automation_tables() -> None:
    tenant, project = _scope_columns()
    op.create_table(
        "automation_corpus_snapshots",
        sa.Column("snapshot_id", sa.Uuid(), primary_key=True),
        tenant,
        project,
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("repository", sa.Text(), nullable=False),
        sa.Column("commit_sha", sa.Text(), nullable=False),
        sa.Column("archive_sha256", sa.Text(), nullable=False),
        sa.Column("acquisition_policy_version", sa.Text(), nullable=False),
        sa.Column("acquisition_policy_hash", sa.Text(), nullable=False),
        sa.Column("acquisition_effect_id", sa.Uuid(), nullable=False),
        sa.Column("acquired_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("compressed_bytes", sa.Integer(), nullable=False),
        sa.Column("expanded_bytes", sa.Integer(), nullable=False),
        sa.Column("workflow_count", sa.Integer(), nullable=False),
        sa.Column("object_ref", sa.Text(), nullable=False),
        sa.Column("object_backend", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("license_state", sa.Text(), nullable=False),
        sa.Column("license_path", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "repository", "commit_sha", "archive_sha256"),
    )
    _add_scope_fks("automation_corpus_snapshots")
    op.create_foreign_key(
        "automation_snapshot_source_fkey",
        "automation_corpus_snapshots",
        "source_records",
        ["source_id"],
        ["source_id"],
    )
    op.create_foreign_key(
        "automation_snapshot_artifact_fkey",
        "automation_corpus_snapshots",
        "source_artifacts",
        ["artifact_id"],
        ["artifact_id"],
    )
    op.create_foreign_key(
        "automation_snapshot_effect_fkey",
        "automation_corpus_snapshots",
        "external_effects",
        ["acquisition_effect_id"],
        ["effect_id"],
    )

    tenant, project = _scope_columns()
    op.create_table(
        "automation_workflow_artifacts",
        sa.Column("workflow_artifact_id", sa.Uuid(), primary_key=True),
        tenant,
        project,
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("raw_hash", sa.Text(), nullable=False),
        sa.Column("raw_size_bytes", sa.Integer(), nullable=False),
        sa.Column("parser_state", sa.Text(), nullable=False),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column(
            "findings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("pattern_lineage_id", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint("snapshot_id", "path", "raw_hash"),
    )
    _add_scope_fks("automation_workflow_artifacts")
    op.create_foreign_key(
        "automation_workflow_snapshot_fkey",
        "automation_workflow_artifacts",
        "automation_corpus_snapshots",
        ["snapshot_id"],
        ["snapshot_id"],
    )
    op.create_foreign_key(
        "automation_workflow_artifact_fkey",
        "automation_workflow_artifacts",
        "source_artifacts",
        ["artifact_id"],
        ["artifact_id"],
    )

    tenant, project = _scope_columns()
    op.create_table(
        "automation_pattern_descriptors",
        sa.Column("descriptor_id", sa.Uuid(), primary_key=True),
        tenant,
        project,
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("pattern_lineage_id", sa.Text(), nullable=False),
        sa.Column("pattern_revision_hash", sa.Text(), nullable=False),
        sa.Column("archetype", sa.Text(), nullable=False),
        sa.Column("guidance_polarity", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "trigger_classes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "action_classes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "integration_classes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "control_flow",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "resilience_controls",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "security_controls",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "observability_controls",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "failure_modes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "required_capabilities",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "stack_constraints",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "source_workflow_refs",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "source_workflow_hashes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("sanitizer_version", sa.Text(), nullable=False),
        sa.Column("scanner_version", sa.Text(), nullable=False),
        sa.Column("descriptor_hash", sa.Text(), nullable=False),
        sa.Column("topology_hash", sa.Text(), nullable=False),
        sa.Column("topology_compiler_version", sa.Text(), nullable=False),
        sa.Column(
            "security_findings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "pii_findings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "secret_findings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "prompt_findings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "implementation_guidance",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "anti_pattern_notes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "auth_pattern",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "retry_error_pattern",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "idempotency_pattern",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "persistence_pattern",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "worker_safe_capsule",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "project_id", "pattern_lineage_id", "pattern_revision_hash"
        ),
        sa.UniqueConstraint("project_id", "descriptor_hash"),
    )
    _add_scope_fks("automation_pattern_descriptors")
    op.create_foreign_key(
        "automation_descriptor_snapshot_fkey",
        "automation_pattern_descriptors",
        "automation_corpus_snapshots",
        ["snapshot_id"],
        ["snapshot_id"],
    )
    op.create_foreign_key(
        "automation_descriptor_artifact_fkey",
        "automation_pattern_descriptors",
        "source_artifacts",
        ["artifact_id"],
        ["artifact_id"],
    )


def _backfill_design_sources() -> None:
    op.execute(
        """
        INSERT INTO source_records (
            source_id, tenant_id, project_id, provider_key, display_name,
            source_domain, source_class, source_kind, source_trust, status,
            policy_revision, config, revoked_at, created_at, updated_at
        )
        SELECT
            source_id, tenant_id, project_id, provider_key, display_name,
            'DESIGN', source_class, adapter_kind,
            CASE
                WHEN source_class IN ('PROJECT_NATIVE','DDE_LIBRARY','ORGANISATION_LIBRARY') THEN 'S2_FIRST_PARTY'
                WHEN source_class IN ('EXTERNAL_REGISTRY','MOBILE_REGISTRY','FIGMA') THEN 'S3_VERIFIED_REGISTRY'
                WHEN source_class = 'DONOR' THEN 'S7_DISCOVERY_ONLY'
                ELSE 'S8_UNTRUSTED'
            END,
            CASE WHEN status IN ('AVAILABLE','DEGRADED','NOT_CONFIGURED','UNAVAILABLE','BLOCKED','DISABLED') THEN status ELSE 'BLOCKED' END,
            'dde-design-source-bridge-v2',
            jsonb_build_object('design_source_id', source_id::text),
            NULL, created_at, updated_at
        FROM design_sources
        ON CONFLICT (source_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO source_artifacts (
            artifact_id, source_id, tenant_id, project_id, parent_artifact_id,
            artifact_kind, provider_artifact_key, title, source_uri, revision,
            content_hash, content_object_ref, content_object_backend,
            content_size_bytes, media_type, metadata, provenance, created_at, updated_at
        )
        SELECT
            artifact_id, source_id, tenant_id, project_id, NULL,
            'DESIGN_' || artifact_kind, provider_artifact_key, title, source_uri,
            COALESCE(version_ref, 'UNVERSIONED'),
            COALESCE(content_hash, 'UNHASHED:' || artifact_id::text),
            content_object_ref, content_object_backend, content_size_bytes, NULL,
            metadata,
            jsonb_build_object(
                'bridge','dde-design-source-bridge-v2',
                'design_retrieval_state', retrieval_state,
                'design_license_state', license_state
            ),
            created_at, updated_at
        FROM design_source_artifacts
        ON CONFLICT (artifact_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO source_admissions (
            admission_id, source_id, artifact_id, tenant_id, project_id,
            content_hash, compiler_version, policy_version, qualification_domain,
            qualification_profile, state, source_trust, reuse_class, analysis,
            hard_failures, validation_obligations, provenance, security_state,
            license_state, provenance_state, sanitization_state, injection_state,
            revoked_at, created_at, updated_at
        )
        SELECT
            a.admission_id, ar.source_id, a.artifact_id, a.tenant_id, a.project_id,
            a.content_hash, a.compiler_version, 'dde-design-source-bridge-v2',
            'DESIGN_SYSTEM', 'DESIGN_SYSTEM', a.state, sr.source_trust,
            CASE ar.license_state
                WHEN 'OPEN_REUSE' THEN 'OPEN_REUSE'
                WHEN 'CONDITIONAL_REUSE' THEN 'CONDITIONAL_REUSE'
                WHEN 'REFERENCE_ONLY' THEN 'REFERENCE_ONLY'
                WHEN 'REJECTED' THEN 'REJECTED'
                ELSE 'UNKNOWN'
            END,
            jsonb_build_object(
                'framework_state', a.framework_state,
                'dependency_state', a.dependency_state,
                'accessibility_state', a.accessibility_state,
                'design_system_state', a.design_system_state,
                'token_mapping_report', a.token_mapping_report,
                'unsupported_behaviors', a.unsupported_behaviors
            ),
            a.hard_failures, a.validation_obligations,
            jsonb_build_object('bridge','dde-design-source-bridge-v2'),
            a.security_state, a.license_state, 'VERIFIED', 'DESIGN_COMPILER', 'UNKNOWN',
            NULL, a.created_at, a.updated_at
        FROM design_source_admissions a
        JOIN design_source_artifacts ar ON ar.artifact_id = a.artifact_id
        JOIN source_records sr ON sr.source_id = ar.source_id
        ON CONFLICT (admission_id) DO NOTHING
        """
    )


def _rewire_vekl_to_neutral() -> None:
    op.drop_constraint(
        "vekl_resources_source_fkey", "vekl_resources", type_="foreignkey"
    )
    op.drop_constraint(
        "vekl_resources_artifact_fkey", "vekl_resources", type_="foreignkey"
    )
    op.create_foreign_key(
        "vekl_resources_source_fkey",
        "vekl_resources",
        "source_records",
        ["source_id"],
        ["source_id"],
    )
    op.create_foreign_key(
        "vekl_resources_artifact_fkey",
        "vekl_resources",
        "source_artifacts",
        ["source_artifact_id"],
        ["artifact_id"],
    )
    op.drop_constraint(
        "vekl_research_findings_source_fkey",
        "vekl_research_findings",
        type_="foreignkey",
    )
    op.drop_constraint(
        "vekl_research_findings_artifact_fkey",
        "vekl_research_findings",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "vekl_research_findings_source_fkey",
        "vekl_research_findings",
        "source_records",
        ["source_id"],
        ["source_id"],
    )
    op.create_foreign_key(
        "vekl_research_findings_artifact_fkey",
        "vekl_research_findings",
        "source_artifacts",
        ["source_artifact_id"],
        ["artifact_id"],
    )


def upgrade() -> None:
    _create_source_tables()
    _create_automation_tables()
    for table in _NEW_TABLES:
        _enable_rls(table)
    _backfill_design_sources()
    _rewire_vekl_to_neutral()


def _assert_design_compatible_downgrade() -> None:
    connection = op.get_bind()
    missing_resources = connection.execute(
        sa.text(
            "SELECT count(*) FROM vekl_resources r "
            "LEFT JOIN design_sources d ON d.source_id = r.source_id "
            "WHERE r.source_id IS NOT NULL AND d.source_id IS NULL"
        )
    ).scalar_one()
    missing_findings = connection.execute(
        sa.text(
            "SELECT count(*) FROM vekl_research_findings r "
            "LEFT JOIN design_sources d ON d.source_id = r.source_id "
            "WHERE r.source_id IS NOT NULL AND d.source_id IS NULL"
        )
    ).scalar_one()
    if missing_resources or missing_findings:
        raise RuntimeError(
            "0040 downgrade refused: VEKL contains neutral-source provenance that cannot be represented by 0039"
        )


def downgrade() -> None:
    _assert_design_compatible_downgrade()
    op.drop_constraint(
        "vekl_research_findings_artifact_fkey",
        "vekl_research_findings",
        type_="foreignkey",
    )
    op.drop_constraint(
        "vekl_research_findings_source_fkey",
        "vekl_research_findings",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "vekl_research_findings_source_fkey",
        "vekl_research_findings",
        "design_sources",
        ["source_id"],
        ["source_id"],
    )
    op.create_foreign_key(
        "vekl_research_findings_artifact_fkey",
        "vekl_research_findings",
        "design_source_artifacts",
        ["source_artifact_id"],
        ["artifact_id"],
    )
    op.drop_constraint(
        "vekl_resources_artifact_fkey", "vekl_resources", type_="foreignkey"
    )
    op.drop_constraint(
        "vekl_resources_source_fkey", "vekl_resources", type_="foreignkey"
    )
    op.create_foreign_key(
        "vekl_resources_source_fkey",
        "vekl_resources",
        "design_sources",
        ["source_id"],
        ["source_id"],
    )
    op.create_foreign_key(
        "vekl_resources_artifact_fkey",
        "vekl_resources",
        "design_source_artifacts",
        ["source_artifact_id"],
        ["artifact_id"],
    )
    for table in reversed(_NEW_TABLES):
        op.drop_table(table)
