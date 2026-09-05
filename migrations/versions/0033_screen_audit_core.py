"""DDE-069 Screen Audit core persistence.

Creates the five canonical Screen Audit objects with tenant/project RLS and
indexes for incremental lookup. Screen Audit derives from PXG/Contract/evidence;
these tables store audit-run state, not a second screen or requirement truth.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0033"
down_revision = "0032"
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
            "WITH CHECK (tenant_id = CAST("
            "current_setting('dde.tenant_id', true) AS uuid) "
            "AND project_id = CAST(current_setting('dde.project_id', true) AS uuid))"
        )
    )


def upgrade() -> None:
    op.create_table(
        "screen_audit_runs",
        sa.Column("audit_run_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=True),
        sa.Column("source_revision", sa.Text(), nullable=True),
        sa.Column("pxg_revision", sa.Integer(), nullable=False),
        sa.Column("frontend_contract_id", sa.Uuid(), nullable=True),
        sa.Column("frontend_contract_version", sa.Integer(), nullable=True),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("role_policy_hash", sa.Text(), nullable=True),
        sa.Column("design_system_hash", sa.Text(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("parent_audit_run_id", sa.Uuid(), nullable=True),
        sa.Column("summary_state", sa.Text(), nullable=False),
        sa.Column("affected_keys", postgresql.JSONB(), nullable=False),
        sa.Column("stale", sa.Boolean(), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("pxg_revision >= 0"),
        sa.CheckConstraint("lock_version >= 1"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.mission_id"]),
        sa.ForeignKeyConstraint(
            ["frontend_contract_id"], ["frontend_contracts.contract_id"]
        ),
        sa.ForeignKeyConstraint(
            ["parent_audit_run_id"], ["screen_audit_runs.audit_run_id"]
        ),
    )
    op.create_index(
        "ix_screen_audit_runs_project_started",
        "screen_audit_runs",
        ["project_id", "started_at"],
    )

    op.create_table(
        "screen_audit_screen_records",
        sa.Column("record_id", sa.Uuid(), primary_key=True),
        sa.Column("audit_run_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("pxg_key", sa.Text(), nullable=False),
        sa.Column("screen_kind", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("module_or_product_area", sa.Text(), nullable=True),
        sa.Column("route_identity", sa.Text(), nullable=True),
        sa.Column("source_refs", postgresql.JSONB(), nullable=False),
        sa.Column("journey_refs", postgresql.JSONB(), nullable=False),
        sa.Column("role_refs", postgresql.JSONB(), nullable=False),
        sa.Column("feature_requirement_refs", postgresql.JSONB(), nullable=False),
        sa.Column("data_dependency_refs", postgresql.JSONB(), nullable=False),
        sa.Column("component_inventory_ref", sa.Text(), nullable=True),
        sa.Column("verification_binding_refs", postgresql.JSONB(), nullable=False),
        sa.Column("render_evidence_refs", postgresql.JSONB(), nullable=False),
        sa.Column("implementation_state", sa.Text(), nullable=False),
        sa.Column("assessment_state", sa.Text(), nullable=False),
        sa.Column("dimension_states", postgresql.JSONB(), nullable=False),
        sa.Column("stale", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint("audit_run_id", "pxg_key"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        sa.ForeignKeyConstraint(["audit_run_id"], ["screen_audit_runs.audit_run_id"]),
    )
    op.create_index(
        "ix_screen_audit_records_project_key",
        "screen_audit_screen_records",
        ["project_id", "pxg_key"],
    )
    op.create_index(
        "ix_screen_audit_records_project_stale",
        "screen_audit_screen_records",
        ["project_id", "stale"],
    )

    op.create_table(
        "screen_audit_findings",
        sa.Column("finding_id", sa.Uuid(), primary_key=True),
        sa.Column("audit_run_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("pxg_key", sa.Text(), nullable=True),
        sa.Column("node_key", sa.Text(), nullable=True),
        sa.Column("finding_type", sa.Text(), nullable=False),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("assessment_state", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=False),
        sa.Column("requirement_refs", postgresql.JSONB(), nullable=False),
        sa.Column("journey_refs", postgresql.JSONB(), nullable=False),
        sa.Column("role_refs", postgresql.JSONB(), nullable=False),
        sa.Column("dependency_keys", postgresql.JSONB(), nullable=False),
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("rule_version", sa.Text(), nullable=False),
        sa.Column("first_detected_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolution_ref", sa.Uuid(), nullable=True),
        sa.Column("decision_ref", sa.Text(), nullable=True),
        sa.Column("stale", sa.Boolean(), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("lock_version >= 1"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        sa.ForeignKeyConstraint(["audit_run_id"], ["screen_audit_runs.audit_run_id"]),
    )
    op.create_index(
        "ix_screen_audit_findings_project_key",
        "screen_audit_findings",
        ["project_id", "pxg_key"],
    )
    op.create_index(
        "ix_screen_audit_findings_project_status",
        "screen_audit_findings",
        ["project_id", "stale", "status"],
    )
    op.create_index(
        "ix_screen_audit_findings_project_dimension",
        "screen_audit_findings",
        ["project_id", "dimension", "severity"],
    )

    op.create_table(
        "screen_audit_evidence",
        sa.Column("evidence_id", sa.Uuid(), primary_key=True),
        sa.Column("audit_run_id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("pxg_key", sa.Text(), nullable=True),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("evidence_kind", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("source_revision", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("assessment_state", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("stale", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        sa.ForeignKeyConstraint(["audit_run_id"], ["screen_audit_runs.audit_run_id"]),
        sa.ForeignKeyConstraint(["finding_id"], ["screen_audit_findings.finding_id"]),
    )
    op.create_index(
        "ix_screen_audit_evidence_project_key",
        "screen_audit_evidence",
        ["project_id", "pxg_key", "stale"],
    )

    op.create_table(
        "screen_audit_resolutions",
        sa.Column("resolution_id", sa.Uuid(), primary_key=True),
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("resolution_kind", sa.Text(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_revision", sa.Text(), nullable=True),
        sa.Column("decision_ref", sa.Text(), nullable=True),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=False),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        sa.ForeignKeyConstraint(["finding_id"], ["screen_audit_findings.finding_id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["frontend_candidates.candidate_id"]),
    )
    op.create_index(
        "ix_screen_audit_resolutions_finding",
        "screen_audit_resolutions",
        ["finding_id"],
    )

    for table in (
        "screen_audit_runs",
        "screen_audit_screen_records",
        "screen_audit_findings",
        "screen_audit_evidence",
        "screen_audit_resolutions",
    ):
        _rls(table)


def downgrade() -> None:
    for table in (
        "screen_audit_resolutions",
        "screen_audit_evidence",
        "screen_audit_findings",
        "screen_audit_screen_records",
        "screen_audit_runs",
    ):
        op.drop_table(table)
