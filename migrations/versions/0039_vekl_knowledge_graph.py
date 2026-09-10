# ruff: noqa: E501
"""Production VEKL unit knowledge graph, deterministic GraphRAG and truth evolution.

Revision ID: 0039
Revises: 0038
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

_KNOWLEDGE_TABLES = (
    "vekl_unit_maps",
    "vekl_knowledge_nodes",
    "vekl_knowledge_edges",
    "vekl_retrieval_routes",
    "vekl_research_findings",
    "vekl_conflict_observations",
    "vekl_truth_challenges",
    "vekl_truth_challenge_findings",
    "vekl_graph_invalidations",
    "vekl_resolution_traces",
    "vekl_execution_knowledge_bindings",
)

_DDL = (
    "CREATE TABLE vekl_unit_maps (\n    unit_map_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    mission_id uuid NOT NULL,\n    task_graph_id uuid NOT NULL,\n    task_graph_version integer NOT NULL,\n    task_ids jsonb NOT NULL DEFAULT '[]'::jsonb,\n    unit_lineage_id text NOT NULL,\n    unit_revision_hash text NOT NULL,\n    unit_boundary_policy_version text NOT NULL,\n    unit_projection_compiler_version text NOT NULL,\n    project_truth_hash text NOT NULL,\n    applicable_truth_slice_hash text NOT NULL,\n    stack_fingerprint_id uuid NOT NULL,\n    stack_fingerprint_hash text NOT NULL,\n    contract_set_hash text NOT NULL,\n    product_experience_hash text,\n    retrieval_route_policy_hash text NOT NULL,\n    objective text NOT NULL,\n    scope jsonb NOT NULL DEFAULT '{}'::jsonb,\n    requirement_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    edr_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    constitution_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    upstream_task_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    downstream_task_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    contracts_consumed jsonb NOT NULL DEFAULT '[]'::jsonb,\n    contracts_produced jsonb NOT NULL DEFAULT '[]'::jsonb,\n    code_targets jsonb NOT NULL DEFAULT '[]'::jsonb,\n    workspace_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    product_experience_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    security_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    eventuality_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    research_questions jsonb NOT NULL DEFAULT '[]'::jsonb,\n    knowledge_route_ids jsonb NOT NULL DEFAULT '[]'::jsonb,\n    required_verifiers jsonb NOT NULL DEFAULT '[]'::jsonb,\n    knowledge_readiness_state text NOT NULL,\n    knowledge_exemption jsonb,\n    challenge_state text NOT NULL,\n    unit_map_hash text NOT NULL,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    invalidated_at timestamptz,\n    invalidation_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,\n    PRIMARY KEY (unit_map_id),\n    UNIQUE (project_id, unit_revision_hash)\n);",
    "CREATE TABLE vekl_knowledge_nodes (\n    knowledge_node_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    node_kind text NOT NULL,\n    object_type text NOT NULL,\n    object_id uuid,\n    stable_ref text NOT NULL,\n    authority_class text NOT NULL,\n    authority_service text NOT NULL,\n    source_revision text,\n    content_hash text NOT NULL,\n    projection_compiler_version text NOT NULL,\n    project_truth_hash text,\n    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    invalidated_at timestamptz,\n    PRIMARY KEY (knowledge_node_id),\n    UNIQUE (project_id, node_kind, stable_ref, content_hash, projection_compiler_version)\n);",
    "CREATE TABLE vekl_knowledge_edges (\n    knowledge_edge_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    from_node_id uuid NOT NULL,\n    relationship text NOT NULL,\n    to_node_id uuid NOT NULL,\n    provenance_ref text NOT NULL,\n    provenance_hash text NOT NULL,\n    derivation_class text NOT NULL,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    invalidated_at timestamptz,\n    PRIMARY KEY (knowledge_edge_id),\n    UNIQUE (project_id, from_node_id, relationship, to_node_id, provenance_hash)\n);",
    "CREATE TABLE vekl_retrieval_routes (\n    route_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    route_slug text NOT NULL,\n    version text NOT NULL,\n    concern text NOT NULL,\n    policy jsonb NOT NULL DEFAULT '{}'::jsonb,\n    policy_hash text NOT NULL,\n    active boolean NOT NULL,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (route_id),\n    UNIQUE (project_id, route_slug, version),\n    UNIQUE (project_id, policy_hash)\n);",
    "CREATE TABLE vekl_research_findings (\n    finding_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    unit_map_id uuid NOT NULL,\n    task_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    concern text NOT NULL,\n    source_id uuid,\n    source_artifact_id uuid,\n    resource_id uuid,\n    source_trust text NOT NULL,\n    source_revision text NOT NULL,\n    content_hash text NOT NULL,\n    claim text NOT NULL,\n    supporting_excerpt_hash text NOT NULL,\n    freshness jsonb NOT NULL DEFAULT '{}'::jsonb,\n    classification text NOT NULL,\n    confidence text NOT NULL,\n    corroboration_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    project_truth_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    stack_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    impact_hypothesis jsonb NOT NULL DEFAULT '[]'::jsonb,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (finding_id)\n);",
    "CREATE TABLE vekl_conflict_observations (\n    observation_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    resource_id uuid NOT NULL,\n    finding_id uuid NOT NULL,\n    current_truth_hash text NOT NULL,\n    conflicting_truth_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    conflict_keys jsonb NOT NULL DEFAULT '[]'::jsonb,\n    source_trust text NOT NULL,\n    freshness jsonb NOT NULL DEFAULT '{}'::jsonb,\n    provenance_valid boolean NOT NULL,\n    activation_rejected boolean NOT NULL,\n    challenge_evaluation_requested boolean NOT NULL,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (observation_id),\n    UNIQUE (project_id, finding_id, current_truth_hash)\n);",
    "CREATE TABLE vekl_truth_challenges (\n    challenge_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    mission_id uuid NOT NULL,\n    task_id uuid,\n    challenge_class text NOT NULL,\n    severity text NOT NULL,\n    status text NOT NULL,\n    current_truth_hash text NOT NULL,\n    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,\n    conflict jsonb NOT NULL DEFAULT '{}'::jsonb,\n    confidence jsonb NOT NULL DEFAULT '{}'::jsonb,\n    impact jsonb NOT NULL DEFAULT '{}'::jsonb,\n    proposal jsonb NOT NULL DEFAULT '{}'::jsonb,\n    decision_analysis jsonb NOT NULL DEFAULT '{}'::jsonb,\n    approval_id uuid,\n    required_role text NOT NULL,\n    decision text,\n    decision_reason text,\n    decided_at timestamptz,\n    reopen_conditions jsonb NOT NULL DEFAULT '[]'::jsonb,\n    challenge_hash text NOT NULL,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (challenge_id),\n    UNIQUE (project_id, challenge_hash)\n);",
    "CREATE TABLE vekl_truth_challenge_findings (\n    challenge_finding_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    challenge_id uuid NOT NULL,\n    finding_id uuid NOT NULL,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (challenge_finding_id),\n    UNIQUE (project_id, challenge_id, finding_id)\n);",
    "CREATE TABLE vekl_graph_invalidations (\n    graph_invalidation_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    unit_map_id uuid,\n    manifest_id uuid,\n    resolution_trace_id uuid,\n    reason_code text NOT NULL,\n    detail jsonb NOT NULL DEFAULT '{}'::jsonb,\n    observed_truth_hash text NOT NULL,\n    previous_hash text,\n    observed_hash text,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (graph_invalidation_id)\n);",
    "CREATE TABLE vekl_resolution_traces (\n    resolution_trace_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    mission_id uuid NOT NULL,\n    task_graph_id uuid NOT NULL,\n    task_ids jsonb NOT NULL DEFAULT '[]'::jsonb,\n    unit_map_id uuid NOT NULL,\n    unit_lineage_id text NOT NULL,\n    unit_revision_hash text NOT NULL,\n    project_truth_hash text NOT NULL,\n    applicable_truth_slice_hash text NOT NULL,\n    stack_fingerprint_hash text NOT NULL,\n    task_signature_hash text NOT NULL,\n    contract_set_hash text NOT NULL,\n    graph_snapshot_hash text NOT NULL,\n    resolution_envelope jsonb NOT NULL DEFAULT '{}'::jsonb,\n    traversed_node_ids jsonb NOT NULL DEFAULT '[]'::jsonb,\n    traversed_edge_ids jsonb NOT NULL DEFAULT '[]'::jsonb,\n    candidate_decisions jsonb NOT NULL DEFAULT '[]'::jsonb,\n    withheld_truth_conflicts jsonb NOT NULL DEFAULT '[]'::jsonb,\n    challenge_observation_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    trace_hash text NOT NULL,\n    created_at timestamptz NOT NULL,\n    PRIMARY KEY (resolution_trace_id),\n    UNIQUE (project_id, trace_hash)\n);",
    "CREATE TABLE vekl_execution_knowledge_bindings (\n    execution_binding_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    resolution_trace_id uuid NOT NULL,\n    binding_stage text NOT NULL,\n    project_truth_hash text NOT NULL,\n    unit_lineage_id text NOT NULL,\n    unit_revision_hash text NOT NULL,\n    graph_revision_hash text NOT NULL,\n    graph_neighbourhood_hash text NOT NULL,\n    applicable_contract_fingerprints jsonb NOT NULL DEFAULT '[]'::jsonb,\n    technical_stack_fingerprint text NOT NULL,\n    knowledge_route_policy_hash text NOT NULL,\n    determinism_envelope_hash text NOT NULL,\n    activation_manifest_id uuid NOT NULL,\n    activation_manifest_hash text NOT NULL,\n    context_package_id uuid,\n    context_package_hash text,\n    context_capsule_hashes jsonb NOT NULL DEFAULT '[]'::jsonb,\n    worker_delivery_hash text NOT NULL,\n    binding_hash text NOT NULL,\n    created_at timestamptz NOT NULL,\n    PRIMARY KEY (execution_binding_id),\n    UNIQUE (project_id, resolution_trace_id, binding_stage),\n    UNIQUE (project_id, binding_hash)\n);",
    "CREATE INDEX ix_vekl_unit_maps_active_lineage ON vekl_unit_maps (project_id, unit_lineage_id) WHERE invalidated_at IS NULL;",
    "CREATE INDEX ix_vekl_knowledge_nodes_active_ref ON vekl_knowledge_nodes (project_id, node_kind, stable_ref) WHERE invalidated_at IS NULL;",
    "CREATE INDEX ix_vekl_knowledge_edges_active_from ON vekl_knowledge_edges (project_id, from_node_id, relationship) WHERE invalidated_at IS NULL;",
    "CREATE INDEX ix_vekl_knowledge_edges_active_to ON vekl_knowledge_edges (project_id, to_node_id, relationship) WHERE invalidated_at IS NULL;",
    "CREATE INDEX ix_vekl_retrieval_routes_active_concern ON vekl_retrieval_routes (project_id, concern) WHERE active;",
    "CREATE INDEX ix_vekl_research_findings_unit_class ON vekl_research_findings (project_id, unit_map_id, classification);",
    "CREATE INDEX ix_vekl_conflict_observations_truth ON vekl_conflict_observations (project_id, current_truth_hash);",
    "CREATE INDEX ix_vekl_truth_challenges_status ON vekl_truth_challenges (project_id, status, severity);",
    "CREATE INDEX ix_vekl_graph_invalidations_unit ON vekl_graph_invalidations (project_id, unit_map_id, created_at);",
    "CREATE INDEX ix_vekl_resolution_traces_unit ON vekl_resolution_traces (project_id, unit_map_id, created_at);",
    "CREATE INDEX ix_vekl_execution_bindings_trace ON vekl_execution_knowledge_bindings (project_id, resolution_trace_id, created_at);",
    "ALTER TABLE vekl_unit_maps ADD CONSTRAINT vekl_unit_map_tenant_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);",
    "ALTER TABLE vekl_unit_maps ADD CONSTRAINT vekl_unit_map_project_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);",
    "ALTER TABLE vekl_unit_maps ADD CONSTRAINT vekl_unit_maps_mission_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);",
    "ALTER TABLE vekl_unit_maps ADD CONSTRAINT vekl_unit_maps_graph_fkey FOREIGN KEY (task_graph_id) REFERENCES task_graphs (graph_id);",
    "ALTER TABLE vekl_unit_maps ADD CONSTRAINT vekl_unit_maps_stack_fkey FOREIGN KEY (stack_fingerprint_id) REFERENCES stack_fingerprints (fingerprint_id);",
    "ALTER TABLE vekl_knowledge_nodes ADD CONSTRAINT vekl_knowledge_node_tenant_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);",
    "ALTER TABLE vekl_knowledge_nodes ADD CONSTRAINT vekl_knowledge_node_project_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);",
    "ALTER TABLE vekl_knowledge_edges ADD CONSTRAINT vekl_knowledge_edge_tenant_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);",
    "ALTER TABLE vekl_knowledge_edges ADD CONSTRAINT vekl_knowledge_edge_project_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);",
    "ALTER TABLE vekl_knowledge_edges ADD CONSTRAINT vekl_knowledge_edges_from_fkey FOREIGN KEY (from_node_id) REFERENCES vekl_knowledge_nodes (knowledge_node_id);",
    "ALTER TABLE vekl_knowledge_edges ADD CONSTRAINT vekl_knowledge_edges_to_fkey FOREIGN KEY (to_node_id) REFERENCES vekl_knowledge_nodes (knowledge_node_id);",
    "ALTER TABLE vekl_retrieval_routes ADD CONSTRAINT vekl_retrieval_route_tenant_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);",
    "ALTER TABLE vekl_retrieval_routes ADD CONSTRAINT vekl_retrieval_route_project_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);",
    "ALTER TABLE vekl_research_findings ADD CONSTRAINT vekl_research_finding_tenant_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);",
    "ALTER TABLE vekl_research_findings ADD CONSTRAINT vekl_research_finding_project_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);",
    "ALTER TABLE vekl_research_findings ADD CONSTRAINT vekl_research_findings_unit_fkey FOREIGN KEY (unit_map_id) REFERENCES vekl_unit_maps (unit_map_id);",
    "ALTER TABLE vekl_research_findings ADD CONSTRAINT vekl_research_findings_source_fkey FOREIGN KEY (source_id) REFERENCES design_sources (source_id);",
    "ALTER TABLE vekl_research_findings ADD CONSTRAINT vekl_research_findings_artifact_fkey FOREIGN KEY (source_artifact_id) REFERENCES design_source_artifacts (artifact_id);",
    "ALTER TABLE vekl_research_findings ADD CONSTRAINT vekl_research_findings_resource_fkey FOREIGN KEY (resource_id) REFERENCES vekl_resources (resource_id);",
    "ALTER TABLE vekl_conflict_observations ADD CONSTRAINT vekl_conflict_observation_tenant_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);",
    "ALTER TABLE vekl_conflict_observations ADD CONSTRAINT vekl_conflict_observation_project_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);",
    "ALTER TABLE vekl_conflict_observations ADD CONSTRAINT vekl_conflict_observations_resource_fkey FOREIGN KEY (resource_id) REFERENCES vekl_resources (resource_id);",
    "ALTER TABLE vekl_conflict_observations ADD CONSTRAINT vekl_conflict_observations_finding_fkey FOREIGN KEY (finding_id) REFERENCES vekl_research_findings (finding_id);",
    "ALTER TABLE vekl_truth_challenges ADD CONSTRAINT vekl_truth_challenge_tenant_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);",
    "ALTER TABLE vekl_truth_challenges ADD CONSTRAINT vekl_truth_challenge_project_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);",
    "ALTER TABLE vekl_truth_challenges ADD CONSTRAINT vekl_truth_challenges_mission_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);",
    "ALTER TABLE vekl_truth_challenges ADD CONSTRAINT vekl_truth_challenges_task_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);",
    "ALTER TABLE vekl_truth_challenges ADD CONSTRAINT vekl_truth_challenges_approval_fkey FOREIGN KEY (approval_id) REFERENCES approvals (approval_id);",
    "ALTER TABLE vekl_truth_challenge_findings ADD CONSTRAINT vekl_truth_challenge_finding_tenant_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);",
    "ALTER TABLE vekl_truth_challenge_findings ADD CONSTRAINT vekl_truth_challenge_finding_project_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);",
    "ALTER TABLE vekl_truth_challenge_findings ADD CONSTRAINT vekl_truth_challenge_findings_challenge_fkey FOREIGN KEY (challenge_id) REFERENCES vekl_truth_challenges (challenge_id);",
    "ALTER TABLE vekl_truth_challenge_findings ADD CONSTRAINT vekl_truth_challenge_findings_finding_fkey FOREIGN KEY (finding_id) REFERENCES vekl_research_findings (finding_id);",
    "ALTER TABLE vekl_graph_invalidations ADD CONSTRAINT vekl_graph_invalidation_tenant_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);",
    "ALTER TABLE vekl_graph_invalidations ADD CONSTRAINT vekl_graph_invalidation_project_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);",
    "ALTER TABLE vekl_graph_invalidations ADD CONSTRAINT vekl_graph_invalidations_unit_fkey FOREIGN KEY (unit_map_id) REFERENCES vekl_unit_maps (unit_map_id);",
    "ALTER TABLE vekl_graph_invalidations ADD CONSTRAINT vekl_graph_invalidations_manifest_fkey FOREIGN KEY (manifest_id) REFERENCES vekl_activation_manifests (manifest_id);",
    "ALTER TABLE vekl_graph_invalidations ADD CONSTRAINT vekl_graph_invalidations_trace_fkey FOREIGN KEY (resolution_trace_id) REFERENCES vekl_resolution_traces (resolution_trace_id);",
    "ALTER TABLE vekl_resolution_traces ADD CONSTRAINT vekl_resolution_trace_tenant_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);",
    "ALTER TABLE vekl_resolution_traces ADD CONSTRAINT vekl_resolution_trace_project_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);",
    "ALTER TABLE vekl_resolution_traces ADD CONSTRAINT vekl_resolution_traces_mission_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);",
    "ALTER TABLE vekl_resolution_traces ADD CONSTRAINT vekl_resolution_traces_graph_fkey FOREIGN KEY (task_graph_id) REFERENCES task_graphs (graph_id);",
    "ALTER TABLE vekl_resolution_traces ADD CONSTRAINT vekl_resolution_traces_unit_fkey FOREIGN KEY (unit_map_id) REFERENCES vekl_unit_maps (unit_map_id);",
    "ALTER TABLE vekl_execution_knowledge_bindings ADD CONSTRAINT vekl_execution_binding_tenant_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);",
    "ALTER TABLE vekl_execution_knowledge_bindings ADD CONSTRAINT vekl_execution_binding_project_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);",
    "ALTER TABLE vekl_execution_knowledge_bindings ADD CONSTRAINT vekl_execution_binding_trace_fkey FOREIGN KEY (resolution_trace_id) REFERENCES vekl_resolution_traces (resolution_trace_id);",
    "ALTER TABLE vekl_execution_knowledge_bindings ADD CONSTRAINT vekl_execution_binding_manifest_fkey FOREIGN KEY (activation_manifest_id) REFERENCES vekl_activation_manifests (manifest_id);",
    "ALTER TABLE vekl_execution_knowledge_bindings ADD CONSTRAINT vekl_execution_binding_context_fkey FOREIGN KEY (context_package_id) REFERENCES context_packages (package_id);",
    "ALTER TABLE vekl_unit_maps ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE vekl_unit_maps FORCE ROW LEVEL SECURITY;",
    "CREATE POLICY vekl_unit_maps_tenant_isolation ON vekl_unit_maps USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));",
    "ALTER TABLE vekl_knowledge_nodes ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE vekl_knowledge_nodes FORCE ROW LEVEL SECURITY;",
    "CREATE POLICY vekl_knowledge_nodes_tenant_isolation ON vekl_knowledge_nodes USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));",
    "ALTER TABLE vekl_knowledge_edges ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE vekl_knowledge_edges FORCE ROW LEVEL SECURITY;",
    "CREATE POLICY vekl_knowledge_edges_tenant_isolation ON vekl_knowledge_edges USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));",
    "ALTER TABLE vekl_retrieval_routes ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE vekl_retrieval_routes FORCE ROW LEVEL SECURITY;",
    "CREATE POLICY vekl_retrieval_routes_tenant_isolation ON vekl_retrieval_routes USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));",
    "ALTER TABLE vekl_research_findings ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE vekl_research_findings FORCE ROW LEVEL SECURITY;",
    "CREATE POLICY vekl_research_findings_tenant_isolation ON vekl_research_findings USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));",
    "ALTER TABLE vekl_conflict_observations ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE vekl_conflict_observations FORCE ROW LEVEL SECURITY;",
    "CREATE POLICY vekl_conflict_observations_tenant_isolation ON vekl_conflict_observations USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));",
    "ALTER TABLE vekl_truth_challenges ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE vekl_truth_challenges FORCE ROW LEVEL SECURITY;",
    "CREATE POLICY vekl_truth_challenges_tenant_isolation ON vekl_truth_challenges USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));",
    "ALTER TABLE vekl_truth_challenge_findings ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE vekl_truth_challenge_findings FORCE ROW LEVEL SECURITY;",
    "CREATE POLICY vekl_truth_challenge_findings_tenant_isolation ON vekl_truth_challenge_findings USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));",
    "ALTER TABLE vekl_graph_invalidations ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE vekl_graph_invalidations FORCE ROW LEVEL SECURITY;",
    "CREATE POLICY vekl_graph_invalidations_tenant_isolation ON vekl_graph_invalidations USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));",
    "ALTER TABLE vekl_resolution_traces ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE vekl_resolution_traces FORCE ROW LEVEL SECURITY;",
    "CREATE POLICY vekl_resolution_traces_tenant_isolation ON vekl_resolution_traces USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));",
    "ALTER TABLE vekl_execution_knowledge_bindings ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE vekl_execution_knowledge_bindings FORCE ROW LEVEL SECURITY;",
    "CREATE POLICY vekl_execution_knowledge_bindings_tenant_isolation ON vekl_execution_knowledge_bindings USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));",
)


def _existing_tables(conn: sa.Connection) -> set[str]:
    return {
        table
        for table in _KNOWLEDGE_TABLES
        if conn.execute(
            sa.text("SELECT to_regclass(:name)"),
            {"name": f"public.{table}"},
        ).scalar()
        is not None
    }


def upgrade() -> None:
    conn = op.get_bind()
    manifest_has_context = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='vekl_activation_manifests' "
            "AND column_name='knowledge_context')"
        )
    ).scalar()
    if not manifest_has_context:
        op.execute(
            sa.text(
                "ALTER TABLE vekl_activation_manifests ADD COLUMN knowledge_context "
                "jsonb NOT NULL DEFAULT '{}'::jsonb"
            )
        )
    existing = _existing_tables(conn)
    if existing:
        if existing != set(_KNOWLEDGE_TABLES):
            missing = sorted(set(_KNOWLEDGE_TABLES) - existing)
            raise RuntimeError(
                "partial Production VEKL knowledge schema detected before migration "
                f"0039; missing tables: {', '.join(missing)}"
            )
        # A fresh database created from the regenerated Stage-1 bundle already
        # contains the exact schema. Incremental 0038 databases do not and run
        # the additive DDL below.
        return
    for statement in _DDL:
        op.execute(sa.text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    for table in reversed(_KNOWLEDGE_TABLES):
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {table} CASCADE"))
    op.execute(
        sa.text(
            "ALTER TABLE vekl_activation_manifests "
            "DROP COLUMN IF EXISTS knowledge_context"
        )
    )
