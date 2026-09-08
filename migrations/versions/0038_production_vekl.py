"""Production VEKL target-application resource fabric.

Revision ID: 0038
Revises: 0037
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def _scope(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON {table} "
        "USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) "
        "AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) "
        "WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) "
        "AND project_id = CAST(current_setting('dde.project_id', true) AS uuid))"
    )


def upgrade() -> None:
    op.add_column("projects", sa.Column("kind", sa.Text(), nullable=True))
    op.create_check_constraint(
        "projects_kind_valid",
        "projects",
        "kind IS NULL OR kind IN ('TARGET_APPLICATION', 'DDE_CONTROL_PLANE')",
    )
    op.create_table(
        "vekl_resources",
        sa.Column("resource_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("parent_resource_id", sa.Uuid()),
        sa.Column("source_id", sa.Uuid()),
        sa.Column("source_artifact_id", sa.Uuid()),
        sa.Column("resource_kind", sa.Text(), nullable=False),
        sa.Column("component_kind", sa.Text()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.Text(), nullable=False),
        sa.Column("source_uri", sa.Text()),
        sa.Column("revision", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("source_trust", sa.Text(), nullable=False),
        sa.Column("reuse_class", sa.Text(), nullable=False),
        sa.Column("lifecycle_state", sa.Text(), nullable=False),
        sa.Column("activation_modes", postgresql.JSONB(), nullable=False),
        sa.Column("exact_versions", postgresql.JSONB(), nullable=False),
        sa.Column("license_ids", postgresql.JSONB(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column("required_capabilities", postgresql.JSONB(), nullable=False),
        sa.Column("filesystem_scopes", postgresql.JSONB(), nullable=False),
        sa.Column("network_scopes", postgresql.JSONB(), nullable=False),
        sa.Column("secret_scopes", postgresql.JSONB(), nullable=False),
        sa.Column("sandbox_requirements", postgresql.JSONB(), nullable=False),
        sa.Column("side_effect_class", sa.Text(), nullable=False),
        sa.Column("required_verifiers", postgresql.JSONB(), nullable=False),
        sa.Column("stack_constraints", postgresql.JSONB(), nullable=False),
        sa.Column("truth_constraints", postgresql.JSONB(), nullable=False),
        sa.Column("freshness", postgresql.JSONB(), nullable=False),
        sa.Column("budget", postgresql.JSONB(), nullable=False),
        sa.Column("injection_findings", postgresql.JSONB(), nullable=False),
        sa.Column("content_excerpt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.tenant_id"], name="vekl_resources_tenant_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], name="vekl_resources_project_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["parent_resource_id"],
            ["vekl_resources.resource_id"],
            name="vekl_resources_parent_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["design_sources.source_id"],
            name="vekl_resources_source_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"],
            ["design_source_artifacts.artifact_id"],
            name="vekl_resources_artifact_fkey",
        ),
    )
    op.create_table(
        "stack_fingerprints",
        sa.Column("fingerprint_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("project_truth_hash", sa.Text(), nullable=False),
        sa.Column("facts", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=False),
        sa.Column("fingerprint_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.tenant_id"], name="stack_fingerprints_tenant_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            name="stack_fingerprints_project_fkey",
        ),
        sa.UniqueConstraint(
            "project_id", "fingerprint_hash", name="uq_stack_fingerprints_hash"
        ),
    )
    op.create_table(
        "task_signatures",
        sa.Column("signature_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint_id", sa.Uuid(), nullable=False),
        sa.Column("lifecycle_stage", sa.Text(), nullable=False),
        sa.Column("task_class", sa.Text(), nullable=False),
        sa.Column("constraints", postgresql.JSONB(), nullable=False),
        sa.Column("risk_category", sa.Text(), nullable=False),
        sa.Column("error_signatures", postgresql.JSONB()),
        sa.Column("required_capabilities", postgresql.JSONB(), nullable=False),
        sa.Column("allowed_filesystem_scopes", postgresql.JSONB()),
        sa.Column("allowed_network_scopes", postgresql.JSONB()),
        sa.Column("allowed_secret_scopes", postgresql.JSONB()),
        sa.Column("required_verifiers", postgresql.JSONB(), nullable=False),
        sa.Column("freshness_needs", postgresql.JSONB(), nullable=False),
        sa.Column("budget", postgresql.JSONB(), nullable=False),
        sa.Column("signature_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.tenant_id"], name="task_signatures_tenant_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], name="task_signatures_project_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.task_id"], name="task_signatures_task_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["fingerprint_id"],
            ["stack_fingerprints.fingerprint_id"],
            name="task_signatures_fingerprint_fkey",
        ),
        sa.UniqueConstraint(
            "task_id", "signature_hash", name="uq_task_signatures_hash"
        ),
    )
    op.create_table(
        "vekl_activation_manifests",
        sa.Column("manifest_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid()),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("task_attempt_id", sa.Uuid()),
        sa.Column("worker_run_id", sa.Uuid()),
        sa.Column("task_signature_id", sa.Uuid(), nullable=False),
        sa.Column("stack_fingerprint_id", sa.Uuid(), nullable=False),
        sa.Column("project_truth_hash", sa.Text(), nullable=False),
        sa.Column("stack_fingerprint_hash", sa.Text(), nullable=False),
        sa.Column("policy_hash", sa.Text(), nullable=False),
        sa.Column("selected_resources", postgresql.JSONB(), nullable=False),
        sa.Column("tools", postgresql.JSONB(), nullable=False),
        sa.Column("hooks", postgresql.JSONB(), nullable=False),
        sa.Column("loops", postgresql.JSONB(), nullable=False),
        sa.Column("community_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("freshness_state", postgresql.JSONB(), nullable=False),
        sa.Column("manifest_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.tenant_id"], name="vekl_manifests_tenant_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], name="vekl_manifests_project_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"], ["missions.mission_id"], name="vekl_manifests_mission_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.task_id"], name="vekl_manifests_task_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["task_attempt_id"],
            ["task_attempts.attempt_id"],
            name="vekl_manifests_attempt_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["worker_run_id"], ["worker_runs.run_id"], name="vekl_manifests_run_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["task_signature_id"],
            ["task_signatures.signature_id"],
            name="vekl_manifests_signature_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["stack_fingerprint_id"],
            ["stack_fingerprints.fingerprint_id"],
            name="vekl_manifests_fingerprint_fkey",
        ),
        sa.UniqueConstraint(
            "project_id", "manifest_hash", name="uq_vekl_manifests_hash"
        ),
    )
    op.create_table(
        "vekl_manifest_invalidations",
        sa.Column("invalidation_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("manifest_id", sa.Uuid(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
        sa.Column("observed_policy_hash", sa.Text(), nullable=False),
        sa.Column("observed_truth_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.tenant_id"], name="vekl_invalidations_tenant_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            name="vekl_invalidations_project_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["manifest_id"],
            ["vekl_activation_manifests.manifest_id"],
            name="vekl_invalidations_manifest_fkey",
        ),
        sa.UniqueConstraint(
            "manifest_id",
            "observed_policy_hash",
            "observed_truth_hash",
            name="uq_vekl_invalidations_observation",
        ),
    )
    op.create_table(
        "vekl_resource_outcomes",
        sa.Column("outcome_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("manifest_id", sa.Uuid(), nullable=False),
        sa.Column("resource_revisions", postgresql.JSONB(), nullable=False),
        sa.Column("verifier_refs", postgresql.JSONB(), nullable=False),
        sa.Column("verified_outcome", sa.Text(), nullable=False),
        sa.Column("regressions", postgresql.JSONB(), nullable=False),
        sa.Column("iterations", sa.Integer(), nullable=False),
        sa.Column("rework", postgresql.JSONB(), nullable=False),
        sa.Column("cost", postgresql.JSONB(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("failure_signatures", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=False),
        sa.Column("recorded_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.tenant_id"], name="vekl_outcomes_tenant_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], name="vekl_outcomes_project_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["manifest_id"],
            ["vekl_activation_manifests.manifest_id"],
            name="vekl_outcomes_manifest_fkey",
        ),
    )
    for table in (
        "vekl_resources",
        "stack_fingerprints",
        "task_signatures",
        "vekl_activation_manifests",
        "vekl_manifest_invalidations",
        "vekl_resource_outcomes",
    ):
        _scope(table)


def downgrade() -> None:
    for table in (
        "vekl_resource_outcomes",
        "vekl_manifest_invalidations",
        "vekl_activation_manifests",
        "task_signatures",
        "stack_fingerprints",
        "vekl_resources",
    ):
        op.drop_table(table)
    op.drop_constraint("projects_kind_valid", "projects", type_="check")
    op.drop_column("projects", "kind")
