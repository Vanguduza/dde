# ruff: noqa: E501
"""EDR-0019 Amendment 1: the five cross-system feature gaps.

Discovery graph trust projection, provider model availability discovery, the adaptive
execution runner, guided frontend design orchestration and the VATI/VTIL knowledge
borrowing model. Statements are the generated DDL from schemas/objects.

Revision ID: 0042
Revises: 0041
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


_CREATE_TABLES = (
    """CREATE TABLE graph_trust_projections (
    projection_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    candidate_id uuid,
    resource_id uuid,
    knowledge_node_id uuid,
    subject_kind text NOT NULL,
    projected_trust text NOT NULL,
    authority_ceiling text NOT NULL,
    allowed_uses jsonb NOT NULL DEFAULT '[]'::jsonb,
    forbidden_uses jsonb NOT NULL DEFAULT '[]'::jsonb,
    guidance_polarity text NOT NULL,
    graph_revision text NOT NULL,
    projection_hash text NOT NULL,
    retrievable boolean NOT NULL,
    satisfies_positive_slots boolean NOT NULL,
    projected_at timestamptz NOT NULL,
    invalidated_at timestamptz,
    invalidation_reason text,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (projection_id),
    CHECK ((guidance_polarity = 'POSITIVE') OR (NOT satisfies_positive_slots)),
    CHECK ((invalidated_at IS NULL) OR (NOT retrievable))
);""",
    """CREATE TABLE provider_model_availability (
    availability_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    provider_id text NOT NULL,
    model_identity text NOT NULL,
    harness_id text,
    discovered_via text NOT NULL,
    available boolean NOT NULL,
    deprecated boolean NOT NULL,
    attested boolean NOT NULL,
    context_window integer,
    supports_tools boolean,
    supports_streaming boolean,
    cost_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    readiness_snapshot_id uuid,
    evidence_pointer text,
    first_seen_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (availability_id),
    UNIQUE (tenant_id, project_id, provider_id, model_identity)
);""",
    """CREATE TABLE adaptive_execution_runs (
    adaptive_run_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    task_id uuid,
    placement_id uuid NOT NULL,
    task_execution_descriptor_ref text,
    attempt integer NOT NULL,
    state text NOT NULL,
    checkpoint_kind text,
    carried_work_state_hash text,
    carried_diff_hash text,
    carried_context_hash text,
    completed_verifier_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    previous_adaptive_run_id uuid,
    fallback_reason text,
    provider_lease_id uuid,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (adaptive_run_id),
    CHECK ((state <> 'FALLBACK_APPLIED') OR (checkpoint_kind IS NOT NULL))
);""",
    """CREATE TABLE frontend_design_orchestrations (
    orchestration_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    research_packet_id uuid,
    design_session_id uuid,
    frontend_contract_ref text,
    screen_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    guidance_dimensions jsonb NOT NULL DEFAULT '[]'::jsonb,
    guidance_findings jsonb NOT NULL DEFAULT '[]'::jsonb,
    proposed_candidate_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    applied_mutation_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    state text NOT NULL,
    authority text NOT NULL,
    verification_satisfied boolean NOT NULL,
    rejected_reason text,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (orchestration_id),
    CHECK (NOT verification_satisfied)
);""",
    """CREATE TABLE knowledge_borrow_grants (
    borrow_grant_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    lender_project_id uuid NOT NULL,
    lender_tenant_id uuid NOT NULL,
    authorized_by_principal_id uuid,
    authority_class text NOT NULL,
    resource_selector jsonb NOT NULL DEFAULT '{}'::jsonb,
    requested_resource_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    materialized_resource_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    trust_ceiling text NOT NULL,
    allowed_uses jsonb NOT NULL DEFAULT '[]'::jsonb,
    forbidden_uses jsonb NOT NULL DEFAULT '[]'::jsonb,
    includes_derived_learning boolean NOT NULL,
    state text NOT NULL,
    refusal_reason text,
    revocation_reason text,
    provenance_hash text NOT NULL,
    materialized_at timestamptz,
    expires_at timestamptz,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (borrow_grant_id),
    CHECK (lender_project_id <> project_id),
    CHECK ((NOT includes_derived_learning) OR (trust_ceiling = 'S7_DISCOVERY_ONLY'))
);""",
)

_FOREIGN_KEYS = (
    """ALTER TABLE graph_trust_projections ADD CONSTRAINT graph_trust_projections_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);""",
    """ALTER TABLE graph_trust_projections ADD CONSTRAINT graph_trust_projections_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);""",
    """ALTER TABLE graph_trust_projections ADD CONSTRAINT graph_trust_projections_candidate_fkey FOREIGN KEY (candidate_id) REFERENCES discovery_candidates (candidate_id);""",
    """ALTER TABLE graph_trust_projections ADD CONSTRAINT graph_trust_projections_resource_fkey FOREIGN KEY (resource_id) REFERENCES vekl_resources (resource_id);""",
    """ALTER TABLE provider_model_availability ADD CONSTRAINT provider_model_availability_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);""",
    """ALTER TABLE provider_model_availability ADD CONSTRAINT provider_model_availability_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);""",
    """ALTER TABLE provider_model_availability ADD CONSTRAINT provider_model_availability_readiness_fkey FOREIGN KEY (readiness_snapshot_id) REFERENCES provider_readiness_snapshots (readiness_snapshot_id);""",
    """ALTER TABLE adaptive_execution_runs ADD CONSTRAINT adaptive_execution_runs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);""",
    """ALTER TABLE adaptive_execution_runs ADD CONSTRAINT adaptive_execution_runs_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);""",
    """ALTER TABLE adaptive_execution_runs ADD CONSTRAINT adaptive_execution_runs_placement_fkey FOREIGN KEY (placement_id) REFERENCES execution_placement_decisions (placement_id);""",
    """ALTER TABLE adaptive_execution_runs ADD CONSTRAINT adaptive_execution_runs_mission_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);""",
    """ALTER TABLE adaptive_execution_runs ADD CONSTRAINT adaptive_execution_runs_task_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);""",
    """ALTER TABLE adaptive_execution_runs ADD CONSTRAINT adaptive_execution_runs_lease_fkey FOREIGN KEY (provider_lease_id) REFERENCES capability_leases (lease_id);""",
    """ALTER TABLE frontend_design_orchestrations ADD CONSTRAINT frontend_design_orchestrations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);""",
    """ALTER TABLE frontend_design_orchestrations ADD CONSTRAINT frontend_design_orchestrations_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);""",
    """ALTER TABLE frontend_design_orchestrations ADD CONSTRAINT frontend_design_orchestrations_packet_fkey FOREIGN KEY (research_packet_id) REFERENCES research_packets (packet_id);""",
    """ALTER TABLE knowledge_borrow_grants ADD CONSTRAINT knowledge_borrow_grants_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);""",
    """ALTER TABLE knowledge_borrow_grants ADD CONSTRAINT knowledge_borrow_grants_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);""",
)

_INDEXES = (
    """CREATE INDEX graph_trust_projections_subject_idx ON graph_trust_projections (tenant_id, project_id, subject_kind);""",
    """CREATE INDEX knowledge_borrow_grants_lender_idx ON knowledge_borrow_grants (tenant_id, project_id, lender_project_id);""",
)

_ROW_LEVEL_SECURITY = (
    """ALTER TABLE graph_trust_projections ENABLE ROW LEVEL SECURITY;""",
    """ALTER TABLE graph_trust_projections FORCE ROW LEVEL SECURITY;""",
    """CREATE POLICY graph_trust_projections_tenant_isolation ON graph_trust_projections USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));""",
    """ALTER TABLE provider_model_availability ENABLE ROW LEVEL SECURITY;""",
    """ALTER TABLE provider_model_availability FORCE ROW LEVEL SECURITY;""",
    """CREATE POLICY provider_model_availability_tenant_isolation ON provider_model_availability USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));""",
    """ALTER TABLE adaptive_execution_runs ENABLE ROW LEVEL SECURITY;""",
    """ALTER TABLE adaptive_execution_runs FORCE ROW LEVEL SECURITY;""",
    """CREATE POLICY adaptive_execution_runs_tenant_isolation ON adaptive_execution_runs USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));""",
    """ALTER TABLE frontend_design_orchestrations ENABLE ROW LEVEL SECURITY;""",
    """ALTER TABLE frontend_design_orchestrations FORCE ROW LEVEL SECURITY;""",
    """CREATE POLICY frontend_design_orchestrations_tenant_isolation ON frontend_design_orchestrations USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));""",
    """ALTER TABLE knowledge_borrow_grants ENABLE ROW LEVEL SECURITY;""",
    """ALTER TABLE knowledge_borrow_grants FORCE ROW LEVEL SECURITY;""",
    """CREATE POLICY knowledge_borrow_grants_tenant_isolation ON knowledge_borrow_grants USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));""",
)

_TABLES = (
    "graph_trust_projections",
    "provider_model_availability",
    "adaptive_execution_runs",
    "frontend_design_orchestrations",
    "knowledge_borrow_grants",
)


def _existing_0042_tables() -> set[str]:
    connection = op.get_bind()
    return {
        table
        for table in _TABLES
        if connection.execute(
            sa.text("SELECT to_regclass(:name)"), {"name": f"public.{table}"}
        ).scalar()
        is not None
    }


def upgrade() -> None:
    # Migration 0001 replays the generated stage1 SQL, which already contains these
    # tables, so a database built from base arrives here with them present. Same
    # convention as 0040/0041: skip when complete, refuse a partial schema.
    existing = _existing_0042_tables()
    if existing:
        if existing != set(_TABLES):
            missing = sorted(set(_TABLES) - existing)
            raise RuntimeError(
                "partial cross-system amendment schema detected before migration 0042; "
                f"missing tables: {', '.join(missing)}"
            )
        return
    for statement in _CREATE_TABLES:
        op.execute(statement)
    for statement in _FOREIGN_KEYS:
        op.execute(statement)
    for statement in _INDEXES:
        op.execute(statement)
    for statement in _ROW_LEVEL_SECURITY:
        op.execute(statement)


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
