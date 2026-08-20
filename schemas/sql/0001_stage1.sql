-- GENERATED from schemas/objects. Do not edit.

CREATE TABLE tenants (
    tenant_id uuid NOT NULL,
    slug text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id)
);

CREATE TABLE projects (
    project_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    slug text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (project_id),
    UNIQUE (tenant_id, slug)
);

CREATE TABLE principals (
    principal_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    slug text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (principal_id),
    UNIQUE (tenant_id, slug)
);

CREATE TABLE principal_grants (
    grant_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid,
    principal_id uuid NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (grant_id)
);

CREATE TABLE capabilities (
    descriptor_id uuid NOT NULL,
    capability_id text NOT NULL,
    version text NOT NULL,
    category text NOT NULL,
    summary text NOT NULL,
    interface_schema_ref text,
    input_schema_ref text,
    output_schema_ref text,
    implementations jsonb NOT NULL DEFAULT '[]'::jsonb,
    supported_worker_profiles jsonb NOT NULL DEFAULT '[]'::jsonb,
    supported_environments jsonb NOT NULL DEFAULT '[]'::jsonb,
    supported_workloads jsonb NOT NULL DEFAULT '[]'::jsonb,
    risk_class text NOT NULL,
    side_effect_class text NOT NULL,
    enforcement_tier text NOT NULL,
    permission_model jsonb NOT NULL DEFAULT '{}'::jsonb,
    cost_model jsonb NOT NULL DEFAULT '{}'::jsonb,
    network_requirements jsonb NOT NULL DEFAULT '{}'::jsonb,
    dependencies jsonb NOT NULL DEFAULT '[]'::jsonb,
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    certification_status text NOT NULL,
    lifecycle_status text NOT NULL,
    visibility text NOT NULL,
    owner_tenant_id uuid,
    supersedes_descriptor_id uuid,
    superseded_by_descriptor_id uuid,
    descriptor_hash text NOT NULL,
    registered_by text NOT NULL,
    deprecated_at timestamptz,
    retired_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (descriptor_id),
    UNIQUE (capability_id, version)
);

CREATE TABLE product_constitution_versions (
    version_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    version integer NOT NULL,
    status text NOT NULL,
    body_markdown text NOT NULL,
    content_hash text NOT NULL,
    supersedes_id uuid,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (version_id),
    UNIQUE (project_id, version)
);

CREATE TABLE requirements (
    requirement_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    slug text NOT NULL,
    statement text NOT NULL,
    constraints jsonb NOT NULL DEFAULT '[]'::jsonb,
    acceptance_conditions jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL,
    supersedes_id uuid,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (requirement_id),
    UNIQUE (project_id, slug)
);

CREATE TABLE edrs (
    edr_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    slug text NOT NULL,
    context text NOT NULL,
    alternatives jsonb NOT NULL DEFAULT '[]'::jsonb,
    decision text NOT NULL,
    rationale text NOT NULL,
    consequences jsonb NOT NULL DEFAULT '[]'::jsonb,
    affected_requirement_slugs jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL,
    supersedes_id uuid,
    decided_by_principal uuid,
    decided_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (edr_id),
    UNIQUE (project_id, slug)
);

CREATE TABLE missions (
    mission_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    slug text NOT NULL,
    title text NOT NULL,
    intent text NOT NULL,
    success_definition text NOT NULL,
    scope jsonb NOT NULL DEFAULT '[]'::jsonb,
    requirement_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL,
    autonomy_ceiling integer NOT NULL,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (mission_id),
    UNIQUE (project_id, slug)
);

CREATE TABLE task_graphs (
    graph_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    version integer NOT NULL,
    supersedes_id uuid,
    status text NOT NULL,
    planning_mode text NOT NULL,
    planner_policy_version text NOT NULL,
    rationale text NOT NULL,
    open_questions jsonb NOT NULL DEFAULT '[]'::jsonb,
    graph_hash text NOT NULL,
    created_by_principal uuid NOT NULL,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (graph_id),
    UNIQUE (mission_id, version)
);

CREATE TABLE tasks (
    task_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    graph_id uuid NOT NULL,
    parent_task_id uuid,
    title text NOT NULL,
    intent text NOT NULL,
    task_class text NOT NULL,
    requirement_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    feature_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    success_criteria jsonb NOT NULL DEFAULT '[]'::jsonb,
    expected_write_scope jsonb NOT NULL DEFAULT '[]'::jsonb,
    expected_read_scope jsonb NOT NULL DEFAULT '[]'::jsonb,
    blast_radius text NOT NULL,
    risk_class text NOT NULL,
    estimated_effort text NOT NULL,
    autonomy_ceiling integer NOT NULL,
    requires_approval boolean NOT NULL,
    verification_profile_ref text,
    status text NOT NULL,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (task_id)
);

CREATE TABLE task_graph_edges (
    edge_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    graph_id uuid NOT NULL,
    from_task_id uuid NOT NULL,
    to_task_id uuid NOT NULL,
    edge_type text NOT NULL,
    contract_ref text,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (edge_id)
);

CREATE TABLE context_packages (
    package_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    version integer NOT NULL,
    assembly_hash text NOT NULL,
    index_version text NOT NULL,
    index_lag_commits integer NOT NULL,
    coverage jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL,
    retrievers_used jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (package_id),
    UNIQUE (task_id, version)
);

CREATE TABLE route_decisions (
    decision_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
    selected_worker_profile_id text NOT NULL,
    workload_class text NOT NULL,
    required_capabilities jsonb NOT NULL DEFAULT '[]'::jsonb,
    required_environment_class text NOT NULL,
    reason_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
    predicted_success numeric,
    predicted_cost numeric,
    predicted_latency numeric,
    confidence numeric,
    selection_source text NOT NULL,
    selection_propensity numeric NOT NULL,
    fallback_plan jsonb NOT NULL DEFAULT '[]'::jsonb,
    escalation_plan jsonb NOT NULL DEFAULT '[]'::jsonb,
    policy_version text NOT NULL,
    decision_hash text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (decision_id)
);

CREATE TABLE execution_environments (
    environment_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    "class" text NOT NULL,
    "type" text NOT NULL,
    os_family text NOT NULL,
    architecture text NOT NULL,
    runtime_image text NOT NULL,
    image_digest text NOT NULL,
    toolchain_manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
    toolchain_manifest_hash text NOT NULL,
    resource_limits jsonb NOT NULL DEFAULT '{}'::jsonb,
    network_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    filesystem_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    isolation_level text NOT NULL,
    credential_profile_id uuid,
    security_profile_id uuid,
    capability_compatibility jsonb NOT NULL DEFAULT '{}'::jsonb,
    worker_compatibility jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL,
    health_status text NOT NULL,
    lifecycle_state text NOT NULL,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (environment_id)
);

CREATE TABLE workspaces (
    workspace_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    task_id uuid,
    execution_environment_id uuid,
    base_revision text,
    current_revision text,
    workspace_path text,
    policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id)
);

CREATE TABLE write_scope_leases (
    lease_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    scope_patterns jsonb NOT NULL DEFAULT '[]'::jsonb,
    exclusive boolean NOT NULL,
    status text NOT NULL,
    acquired_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    released_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (lease_id)
);

CREATE TABLE execution_plans (
    plan_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    route_decision_id uuid NOT NULL,
    context_package_id uuid NOT NULL,
    worker_profile_id text NOT NULL,
    execution_environment_id uuid NOT NULL,
    workspace_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    capability_requirements jsonb NOT NULL DEFAULT '[]'::jsonb,
    enforcement_tier text NOT NULL,
    autonomy_level integer NOT NULL,
    resource_budget jsonb NOT NULL DEFAULT '{}'::jsonb,
    time_budget jsonb NOT NULL DEFAULT '{}'::jsonb,
    token_budget jsonb NOT NULL DEFAULT '{}'::jsonb,
    network_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    filesystem_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    verification_plan_id uuid,
    acceptance_oracle_id uuid,
    write_scope_lease_id uuid,
    checkpoint_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    retry_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    escalation_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    plan_hash text NOT NULL,
    status text NOT NULL,
    approved_at timestamptz,
    started_at timestamptz,
    ended_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (plan_id)
);

CREATE TABLE task_attempts (
    attempt_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    sequence integer NOT NULL,
    execution_plan_id uuid NOT NULL,
    input_context_hash text NOT NULL,
    workspace_revision text NOT NULL,
    result_artifact_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    verification_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    integration_proposal_id uuid,
    status text NOT NULL,
    failure_class text,
    retry_of uuid,
    checkpoint_id uuid,
    started_at timestamptz,
    ended_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (attempt_id),
    UNIQUE (task_id, sequence)
);

CREATE TABLE worker_runs (
    run_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_attempt_id uuid NOT NULL,
    sequence integer NOT NULL,
    execution_plan_id uuid NOT NULL,
    worker_session_id uuid,
    worker_id text NOT NULL,
    worker_profile_id text NOT NULL,
    environment_id uuid NOT NULL,
    workspace_id uuid NOT NULL,
    context_package_id uuid NOT NULL,
    policy_version text NOT NULL,
    lease_set_hash text NOT NULL,
    checkpoint_id uuid,
    status text NOT NULL,
    failure_class text,
    usage_record_id uuid,
    artifact_manifest_id uuid,
    started_at timestamptz,
    ended_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (run_id),
    UNIQUE (task_attempt_id, sequence)
);

CREATE TABLE worker_events (
    event_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    run_id uuid NOT NULL,
    task_id uuid NOT NULL,
    sequence integer NOT NULL,
    event_type text NOT NULL,
    occurred_at timestamptz NOT NULL,
    actor text NOT NULL,
    correlation_id text NOT NULL,
    causation_id text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    schema_version text NOT NULL,
    integrity_hash text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (event_id, occurred_at),
    UNIQUE (run_id, sequence, occurred_at)
) PARTITION BY RANGE (occurred_at);
CREATE TABLE worker_events_default PARTITION OF worker_events DEFAULT;

CREATE TABLE capability_leases (
    lease_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    execution_plan_id uuid NOT NULL,
    worker_run_id uuid,
    environment_id uuid,
    capability_id text NOT NULL,
    capability_version text NOT NULL,
    resource_scope jsonb NOT NULL DEFAULT '{}'::jsonb,
    operation_scope text NOT NULL,
    constraints jsonb NOT NULL DEFAULT '{}'::jsonb,
    issued_by_policy_version text NOT NULL,
    issued_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    revocable boolean NOT NULL,
    status text NOT NULL,
    denied_reason text,
    revoked_at timestamptz,
    revocation_reason text,
    lease_hash text NOT NULL,
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (lease_id)
);

CREATE TABLE credential_handles (
    handle_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    worker_run_id uuid,
    lease_id uuid NOT NULL,
    capability_id text NOT NULL,
    provider_id text NOT NULL,
    provider_ref text,
    resource_scope jsonb NOT NULL DEFAULT '{}'::jsonb,
    issued_by_policy_version text NOT NULL,
    secret_hash text NOT NULL,
    status text NOT NULL,
    issued_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    revocation_reason text,
    supersedes_handle_id uuid,
    superseded_by_handle_id uuid,
    requested_by text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (handle_id)
);

CREATE TABLE external_effects (
    effect_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    worker_run_id uuid NOT NULL,
    capability_lease_id uuid NOT NULL,
    command_id uuid NOT NULL,
    target_system text NOT NULL,
    target_resource text NOT NULL,
    operation text NOT NULL,
    side_effect_class text NOT NULL,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    status text NOT NULL,
    external_reference text,
    response_hash text,
    reconciliation_method text,
    created_at timestamptz NOT NULL,
    confirmed_at timestamptz,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (effect_id)
);

CREATE TABLE checkpoints (
    checkpoint_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    task_attempt_id uuid NOT NULL,
    worker_run_id uuid NOT NULL,
    context_package_id uuid NOT NULL,
    execution_plan_id uuid NOT NULL,
    completed_work jsonb NOT NULL DEFAULT '[]'::jsonb,
    verified_work jsonb NOT NULL DEFAULT '[]'::jsonb,
    pending_work jsonb NOT NULL DEFAULT '[]'::jsonb,
    known_failures jsonb NOT NULL DEFAULT '[]'::jsonb,
    next_action text NOT NULL,
    do_not_repeat jsonb NOT NULL DEFAULT '[]'::jsonb,
    artifact_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    lease_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    workspace_revision text NOT NULL,
    integration_state text NOT NULL,
    event_sequence integer NOT NULL,
    integrity_hash text NOT NULL,
    command_id uuid NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (checkpoint_id)
);

CREATE TABLE artifacts (
    artifact_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    task_id uuid,
    content_hash text NOT NULL,
    storage_key text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (artifact_id)
);

CREATE TABLE acceptance_oracles (
    oracle_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    oracle_version text NOT NULL,
    scope text NOT NULL,
    requirement_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    feature_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    observable_outcomes jsonb NOT NULL DEFAULT '[]'::jsonb,
    domain_invariants jsonb NOT NULL DEFAULT '[]'::jsonb,
    negative_cases jsonb NOT NULL DEFAULT '[]'::jsonb,
    minimum_confidence numeric NOT NULL,
    human_assertions jsonb NOT NULL DEFAULT '[]'::jsonb,
    approved_by text,
    approved_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (oracle_id)
);

CREATE TABLE verification_runs (
    verification_run_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    task_attempt_id uuid NOT NULL,
    worker_run_id uuid NOT NULL,
    workspace_id uuid NOT NULL,
    oracle_id uuid NOT NULL,
    sequence integer NOT NULL,
    status text NOT NULL,
    confidence numeric NOT NULL,
    check_results jsonb NOT NULL DEFAULT '[]'::jsonb,
    outcome_results jsonb NOT NULL DEFAULT '[]'::jsonb,
    negative_case_results jsonb NOT NULL DEFAULT '[]'::jsonb,
    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    started_at timestamptz NOT NULL,
    ended_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (verification_run_id),
    UNIQUE (worker_run_id, sequence)
);

CREATE TABLE integration_proposals (
    proposal_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    task_attempt_id uuid NOT NULL,
    source_branch text NOT NULL,
    base_revision text NOT NULL,
    proposed_revision text NOT NULL,
    diff_summary text NOT NULL,
    changed_paths jsonb NOT NULL DEFAULT '[]'::jsonb,
    scope_lease_id uuid NOT NULL,
    pre_integration_verification_ref uuid NOT NULL,
    status text NOT NULL,
    conflict_class text,
    attempts integer NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (proposal_id)
);

CREATE TABLE diff_gate_reports (
    report_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    proposal_id uuid NOT NULL,
    command_id uuid NOT NULL,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    base_revision text NOT NULL,
    proposed_revision text NOT NULL,
    changed_paths jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL,
    findings jsonb NOT NULL DEFAULT '[]'::jsonb,
    quarantined boolean NOT NULL,
    sbom_document jsonb NOT NULL DEFAULT '{}'::jsonb,
    sbom_content_hash text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (report_id)
);

CREATE TABLE dependency_admissions (
    admission_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    report_id uuid NOT NULL,
    package_name text NOT NULL,
    package_version text NOT NULL,
    ecosystem text NOT NULL,
    is_top_level boolean NOT NULL,
    licence text,
    maintenance_signal text NOT NULL,
    provenance text NOT NULL,
    vulnerability_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    typosquat_of text,
    justification jsonb,
    transitive_delta integer,
    status text NOT NULL,
    blocking_reason text,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (admission_id)
);

CREATE TABLE evidence (
    evidence_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    verification_run_id uuid NOT NULL,
    integrated_revision text NOT NULL,
    oracle_id uuid,
    outcome_id uuid,
    evidence_type text NOT NULL,
    artifact_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    content_hash text NOT NULL,
    signature text NOT NULL,
    produced_by text NOT NULL,
    independence_flags jsonb NOT NULL DEFAULT '{}'::jsonb,
    recorded_at timestamptz NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (evidence_id)
);

CREATE TABLE events (
    event_id uuid NOT NULL,
    event_type text NOT NULL,
    aggregate_type text NOT NULL,
    aggregate_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    task_id uuid,
    sequence integer NOT NULL,
    occurred_at timestamptz NOT NULL,
    correlation_id text NOT NULL,
    causation_id text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    schema_version text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (event_id, occurred_at)
) PARTITION BY RANGE (occurred_at);
CREATE TABLE events_default PARTITION OF events DEFAULT;

CREATE TABLE outbox (
    outbox_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    event_id uuid NOT NULL,
    status text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    published_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (outbox_id)
);

CREATE TABLE command_idempotency (
    command_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    status text NOT NULL,
    result jsonb,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (command_id),
    UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE audit_events (
    audit_event_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid,
    event_type text NOT NULL,
    sequence integer NOT NULL,
    prev_hash text,
    entry_hash text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (audit_event_id)
);

ALTER TABLE projects ADD CONSTRAINT projects_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);

ALTER TABLE principals ADD CONSTRAINT principals_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);

ALTER TABLE principal_grants ADD CONSTRAINT principal_grants_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE principal_grants ADD CONSTRAINT principal_grants_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE principal_grants ADD CONSTRAINT principal_grants_principal_id_fkey FOREIGN KEY (principal_id) REFERENCES principals (principal_id);

ALTER TABLE capabilities ADD CONSTRAINT capabilities_owner_tenant_id_fkey FOREIGN KEY (owner_tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE capabilities ADD CONSTRAINT capabilities_supersedes_descriptor_id_fkey FOREIGN KEY (supersedes_descriptor_id) REFERENCES capabilities (descriptor_id);
ALTER TABLE capabilities ADD CONSTRAINT capabilities_superseded_by_descriptor_id_fkey FOREIGN KEY (superseded_by_descriptor_id) REFERENCES capabilities (descriptor_id);

ALTER TABLE product_constitution_versions ADD CONSTRAINT product_constitution_versions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE product_constitution_versions ADD CONSTRAINT product_constitution_versions_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE product_constitution_versions ADD CONSTRAINT product_constitution_versions_supersedes_id_fkey FOREIGN KEY (supersedes_id) REFERENCES product_constitution_versions (version_id);

ALTER TABLE requirements ADD CONSTRAINT requirements_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE requirements ADD CONSTRAINT requirements_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE requirements ADD CONSTRAINT requirements_supersedes_id_fkey FOREIGN KEY (supersedes_id) REFERENCES requirements (requirement_id);

ALTER TABLE edrs ADD CONSTRAINT edrs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE edrs ADD CONSTRAINT edrs_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE edrs ADD CONSTRAINT edrs_supersedes_id_fkey FOREIGN KEY (supersedes_id) REFERENCES edrs (edr_id);
ALTER TABLE edrs ADD CONSTRAINT edrs_decided_by_principal_fkey FOREIGN KEY (decided_by_principal) REFERENCES principals (principal_id);

ALTER TABLE missions ADD CONSTRAINT missions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE missions ADD CONSTRAINT missions_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE task_graphs ADD CONSTRAINT task_graphs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE task_graphs ADD CONSTRAINT task_graphs_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE task_graphs ADD CONSTRAINT task_graphs_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE task_graphs ADD CONSTRAINT task_graphs_created_by_principal_fkey FOREIGN KEY (created_by_principal) REFERENCES principals (principal_id);
ALTER TABLE task_graphs ADD CONSTRAINT task_graphs_supersedes_id_fkey FOREIGN KEY (supersedes_id) REFERENCES task_graphs (graph_id);

ALTER TABLE tasks ADD CONSTRAINT tasks_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE tasks ADD CONSTRAINT tasks_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE tasks ADD CONSTRAINT tasks_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE tasks ADD CONSTRAINT tasks_graph_id_fkey FOREIGN KEY (graph_id) REFERENCES task_graphs (graph_id);
ALTER TABLE tasks ADD CONSTRAINT tasks_parent_task_id_fkey FOREIGN KEY (parent_task_id) REFERENCES tasks (task_id);

ALTER TABLE task_graph_edges ADD CONSTRAINT task_graph_edges_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE task_graph_edges ADD CONSTRAINT task_graph_edges_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE task_graph_edges ADD CONSTRAINT task_graph_edges_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE task_graph_edges ADD CONSTRAINT task_graph_edges_graph_id_fkey FOREIGN KEY (graph_id) REFERENCES task_graphs (graph_id);
ALTER TABLE task_graph_edges ADD CONSTRAINT task_graph_edges_from_task_id_fkey FOREIGN KEY (from_task_id) REFERENCES tasks (task_id);
ALTER TABLE task_graph_edges ADD CONSTRAINT task_graph_edges_to_task_id_fkey FOREIGN KEY (to_task_id) REFERENCES tasks (task_id);

ALTER TABLE context_packages ADD CONSTRAINT context_packages_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE context_packages ADD CONSTRAINT context_packages_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE context_packages ADD CONSTRAINT context_packages_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE context_packages ADD CONSTRAINT context_packages_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);

ALTER TABLE route_decisions ADD CONSTRAINT route_decisions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE route_decisions ADD CONSTRAINT route_decisions_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE route_decisions ADD CONSTRAINT route_decisions_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE route_decisions ADD CONSTRAINT route_decisions_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);

ALTER TABLE execution_environments ADD CONSTRAINT execution_environments_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE execution_environments ADD CONSTRAINT execution_environments_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE workspaces ADD CONSTRAINT workspaces_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE workspaces ADD CONSTRAINT workspaces_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE workspaces ADD CONSTRAINT workspaces_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE workspaces ADD CONSTRAINT workspaces_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE workspaces ADD CONSTRAINT workspaces_execution_environment_id_fkey FOREIGN KEY (execution_environment_id) REFERENCES execution_environments (environment_id);

ALTER TABLE write_scope_leases ADD CONSTRAINT write_scope_leases_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE write_scope_leases ADD CONSTRAINT write_scope_leases_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE write_scope_leases ADD CONSTRAINT write_scope_leases_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE write_scope_leases ADD CONSTRAINT write_scope_leases_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);

ALTER TABLE execution_plans ADD CONSTRAINT execution_plans_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE execution_plans ADD CONSTRAINT execution_plans_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE execution_plans ADD CONSTRAINT execution_plans_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE execution_plans ADD CONSTRAINT execution_plans_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE execution_plans ADD CONSTRAINT execution_plans_route_decision_id_fkey FOREIGN KEY (route_decision_id) REFERENCES route_decisions (decision_id);
ALTER TABLE execution_plans ADD CONSTRAINT execution_plans_context_package_id_fkey FOREIGN KEY (context_package_id) REFERENCES context_packages (package_id);
ALTER TABLE execution_plans ADD CONSTRAINT execution_plans_execution_environment_id_fkey FOREIGN KEY (execution_environment_id) REFERENCES execution_environments (environment_id);
ALTER TABLE execution_plans ADD CONSTRAINT execution_plans_write_scope_lease_id_fkey FOREIGN KEY (write_scope_lease_id) REFERENCES write_scope_leases (lease_id);

ALTER TABLE task_attempts ADD CONSTRAINT task_attempts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE task_attempts ADD CONSTRAINT task_attempts_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE task_attempts ADD CONSTRAINT task_attempts_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE task_attempts ADD CONSTRAINT task_attempts_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE task_attempts ADD CONSTRAINT task_attempts_execution_plan_id_fkey FOREIGN KEY (execution_plan_id) REFERENCES execution_plans (plan_id);
ALTER TABLE task_attempts ADD CONSTRAINT task_attempts_retry_of_fkey FOREIGN KEY (retry_of) REFERENCES task_attempts (attempt_id);

ALTER TABLE worker_runs ADD CONSTRAINT worker_runs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE worker_runs ADD CONSTRAINT worker_runs_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE worker_runs ADD CONSTRAINT worker_runs_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE worker_runs ADD CONSTRAINT worker_runs_task_attempt_id_fkey FOREIGN KEY (task_attempt_id) REFERENCES task_attempts (attempt_id);
ALTER TABLE worker_runs ADD CONSTRAINT worker_runs_execution_plan_id_fkey FOREIGN KEY (execution_plan_id) REFERENCES execution_plans (plan_id);
ALTER TABLE worker_runs ADD CONSTRAINT worker_runs_environment_id_fkey FOREIGN KEY (environment_id) REFERENCES execution_environments (environment_id);
ALTER TABLE worker_runs ADD CONSTRAINT worker_runs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces (workspace_id);
ALTER TABLE worker_runs ADD CONSTRAINT worker_runs_context_package_id_fkey FOREIGN KEY (context_package_id) REFERENCES context_packages (package_id);

ALTER TABLE worker_events ADD CONSTRAINT worker_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE worker_events ADD CONSTRAINT worker_events_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE worker_events ADD CONSTRAINT worker_events_run_id_fkey FOREIGN KEY (run_id) REFERENCES worker_runs (run_id);

ALTER TABLE capability_leases ADD CONSTRAINT capability_leases_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE capability_leases ADD CONSTRAINT capability_leases_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE capability_leases ADD CONSTRAINT capability_leases_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE capability_leases ADD CONSTRAINT capability_leases_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE capability_leases ADD CONSTRAINT capability_leases_execution_plan_id_fkey FOREIGN KEY (execution_plan_id) REFERENCES execution_plans (plan_id);

ALTER TABLE credential_handles ADD CONSTRAINT credential_handles_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE credential_handles ADD CONSTRAINT credential_handles_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE credential_handles ADD CONSTRAINT credential_handles_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE credential_handles ADD CONSTRAINT credential_handles_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE credential_handles ADD CONSTRAINT credential_handles_lease_id_fkey FOREIGN KEY (lease_id) REFERENCES capability_leases (lease_id);
ALTER TABLE credential_handles ADD CONSTRAINT credential_handles_supersedes_handle_id_fkey FOREIGN KEY (supersedes_handle_id) REFERENCES credential_handles (handle_id);
ALTER TABLE credential_handles ADD CONSTRAINT credential_handles_superseded_by_handle_id_fkey FOREIGN KEY (superseded_by_handle_id) REFERENCES credential_handles (handle_id);

ALTER TABLE external_effects ADD CONSTRAINT external_effects_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE external_effects ADD CONSTRAINT external_effects_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE external_effects ADD CONSTRAINT external_effects_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE external_effects ADD CONSTRAINT external_effects_capability_lease_id_fkey FOREIGN KEY (capability_lease_id) REFERENCES capability_leases (lease_id);
ALTER TABLE external_effects ADD CONSTRAINT external_effects_command_id_fkey FOREIGN KEY (command_id) REFERENCES command_idempotency (command_id);

ALTER TABLE checkpoints ADD CONSTRAINT checkpoints_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE checkpoints ADD CONSTRAINT checkpoints_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE checkpoints ADD CONSTRAINT checkpoints_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE checkpoints ADD CONSTRAINT checkpoints_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE checkpoints ADD CONSTRAINT checkpoints_task_attempt_id_fkey FOREIGN KEY (task_attempt_id) REFERENCES task_attempts (attempt_id);
ALTER TABLE checkpoints ADD CONSTRAINT checkpoints_worker_run_id_fkey FOREIGN KEY (worker_run_id) REFERENCES worker_runs (run_id);
ALTER TABLE checkpoints ADD CONSTRAINT checkpoints_context_package_id_fkey FOREIGN KEY (context_package_id) REFERENCES context_packages (package_id);
ALTER TABLE checkpoints ADD CONSTRAINT checkpoints_execution_plan_id_fkey FOREIGN KEY (execution_plan_id) REFERENCES execution_plans (plan_id);
ALTER TABLE checkpoints ADD CONSTRAINT checkpoints_command_id_fkey FOREIGN KEY (command_id) REFERENCES command_idempotency (command_id);

ALTER TABLE artifacts ADD CONSTRAINT artifacts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE artifacts ADD CONSTRAINT artifacts_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE artifacts ADD CONSTRAINT artifacts_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);

ALTER TABLE acceptance_oracles ADD CONSTRAINT acceptance_oracles_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE acceptance_oracles ADD CONSTRAINT acceptance_oracles_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE acceptance_oracles ADD CONSTRAINT acceptance_oracles_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE acceptance_oracles ADD CONSTRAINT acceptance_oracles_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);

ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_task_attempt_id_fkey FOREIGN KEY (task_attempt_id) REFERENCES task_attempts (attempt_id);
ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_worker_run_id_fkey FOREIGN KEY (worker_run_id) REFERENCES worker_runs (run_id);
ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces (workspace_id);
ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_oracle_id_fkey FOREIGN KEY (oracle_id) REFERENCES acceptance_oracles (oracle_id);

ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_task_attempt_id_fkey FOREIGN KEY (task_attempt_id) REFERENCES task_attempts (attempt_id);
ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_scope_lease_id_fkey FOREIGN KEY (scope_lease_id) REFERENCES write_scope_leases (lease_id);
ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_verification_ref_fkey FOREIGN KEY (pre_integration_verification_ref) REFERENCES verification_runs (verification_run_id);

ALTER TABLE diff_gate_reports ADD CONSTRAINT diff_gate_reports_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE diff_gate_reports ADD CONSTRAINT diff_gate_reports_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE diff_gate_reports ADD CONSTRAINT diff_gate_reports_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE diff_gate_reports ADD CONSTRAINT diff_gate_reports_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE diff_gate_reports ADD CONSTRAINT diff_gate_reports_proposal_id_fkey FOREIGN KEY (proposal_id) REFERENCES integration_proposals (proposal_id);
ALTER TABLE diff_gate_reports ADD CONSTRAINT diff_gate_reports_command_id_fkey FOREIGN KEY (command_id) REFERENCES command_idempotency (command_id);

ALTER TABLE dependency_admissions ADD CONSTRAINT dependency_admissions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE dependency_admissions ADD CONSTRAINT dependency_admissions_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE dependency_admissions ADD CONSTRAINT dependency_admissions_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE dependency_admissions ADD CONSTRAINT dependency_admissions_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE dependency_admissions ADD CONSTRAINT dependency_admissions_report_id_fkey FOREIGN KEY (report_id) REFERENCES diff_gate_reports (report_id);

ALTER TABLE evidence ADD CONSTRAINT evidence_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE evidence ADD CONSTRAINT evidence_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE evidence ADD CONSTRAINT evidence_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE evidence ADD CONSTRAINT evidence_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE evidence ADD CONSTRAINT evidence_verification_run_id_fkey FOREIGN KEY (verification_run_id) REFERENCES verification_runs (verification_run_id);

ALTER TABLE events ADD CONSTRAINT events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE events ADD CONSTRAINT events_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE outbox ADD CONSTRAINT outbox_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE outbox ADD CONSTRAINT outbox_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE command_idempotency ADD CONSTRAINT command_idempotency_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE command_idempotency ADD CONSTRAINT command_idempotency_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE audit_events ADD CONSTRAINT audit_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE audit_events ADD CONSTRAINT audit_events_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY tenants_tenant_isolation ON tenants USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid));

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects FORCE ROW LEVEL SECURITY;
CREATE POLICY projects_tenant_isolation ON projects USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid));

ALTER TABLE principals ENABLE ROW LEVEL SECURITY;
ALTER TABLE principals FORCE ROW LEVEL SECURITY;
CREATE POLICY principals_tenant_isolation ON principals USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid));

ALTER TABLE principal_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE principal_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY principal_grants_tenant_isolation ON principal_grants USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid));

ALTER TABLE capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE capabilities FORCE ROW LEVEL SECURITY;
CREATE POLICY capabilities_tenant_isolation ON capabilities USING (visibility = 'global' OR owner_tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid)) WITH CHECK (visibility = 'global' OR owner_tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid));

ALTER TABLE product_constitution_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_constitution_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY product_constitution_versions_tenant_isolation ON product_constitution_versions USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE requirements ENABLE ROW LEVEL SECURITY;
ALTER TABLE requirements FORCE ROW LEVEL SECURITY;
CREATE POLICY requirements_tenant_isolation ON requirements USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE edrs ENABLE ROW LEVEL SECURITY;
ALTER TABLE edrs FORCE ROW LEVEL SECURITY;
CREATE POLICY edrs_tenant_isolation ON edrs USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE missions ENABLE ROW LEVEL SECURITY;
ALTER TABLE missions FORCE ROW LEVEL SECURITY;
CREATE POLICY missions_tenant_isolation ON missions USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE task_graphs ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_graphs FORCE ROW LEVEL SECURITY;
CREATE POLICY task_graphs_tenant_isolation ON task_graphs USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks FORCE ROW LEVEL SECURITY;
CREATE POLICY tasks_tenant_isolation ON tasks USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE task_graph_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_graph_edges FORCE ROW LEVEL SECURITY;
CREATE POLICY task_graph_edges_tenant_isolation ON task_graph_edges USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE context_packages ENABLE ROW LEVEL SECURITY;
ALTER TABLE context_packages FORCE ROW LEVEL SECURITY;
CREATE POLICY context_packages_tenant_isolation ON context_packages USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE route_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE route_decisions FORCE ROW LEVEL SECURITY;
CREATE POLICY route_decisions_tenant_isolation ON route_decisions USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE execution_environments ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_environments FORCE ROW LEVEL SECURITY;
CREATE POLICY execution_environments_tenant_isolation ON execution_environments USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces FORCE ROW LEVEL SECURITY;
CREATE POLICY workspaces_tenant_isolation ON workspaces USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE write_scope_leases ENABLE ROW LEVEL SECURITY;
ALTER TABLE write_scope_leases FORCE ROW LEVEL SECURITY;
CREATE POLICY write_scope_leases_tenant_isolation ON write_scope_leases USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE execution_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_plans FORCE ROW LEVEL SECURITY;
CREATE POLICY execution_plans_tenant_isolation ON execution_plans USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE task_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_attempts FORCE ROW LEVEL SECURITY;
CREATE POLICY task_attempts_tenant_isolation ON task_attempts USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE worker_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE worker_runs FORCE ROW LEVEL SECURITY;
CREATE POLICY worker_runs_tenant_isolation ON worker_runs USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE worker_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worker_events FORCE ROW LEVEL SECURITY;
CREATE POLICY worker_events_tenant_isolation ON worker_events USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE capability_leases ENABLE ROW LEVEL SECURITY;
ALTER TABLE capability_leases FORCE ROW LEVEL SECURITY;
CREATE POLICY capability_leases_tenant_isolation ON capability_leases USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE credential_handles ENABLE ROW LEVEL SECURITY;
ALTER TABLE credential_handles FORCE ROW LEVEL SECURITY;
CREATE POLICY credential_handles_tenant_isolation ON credential_handles USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE external_effects ENABLE ROW LEVEL SECURITY;
ALTER TABLE external_effects FORCE ROW LEVEL SECURITY;
CREATE POLICY external_effects_tenant_isolation ON external_effects USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoints FORCE ROW LEVEL SECURITY;
CREATE POLICY checkpoints_tenant_isolation ON checkpoints USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifacts FORCE ROW LEVEL SECURITY;
CREATE POLICY artifacts_tenant_isolation ON artifacts USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE acceptance_oracles ENABLE ROW LEVEL SECURITY;
ALTER TABLE acceptance_oracles FORCE ROW LEVEL SECURITY;
CREATE POLICY acceptance_oracles_tenant_isolation ON acceptance_oracles USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE verification_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_runs FORCE ROW LEVEL SECURITY;
CREATE POLICY verification_runs_tenant_isolation ON verification_runs USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE integration_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_proposals FORCE ROW LEVEL SECURITY;
CREATE POLICY integration_proposals_tenant_isolation ON integration_proposals USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE diff_gate_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE diff_gate_reports FORCE ROW LEVEL SECURITY;
CREATE POLICY diff_gate_reports_tenant_isolation ON diff_gate_reports USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE dependency_admissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE dependency_admissions FORCE ROW LEVEL SECURITY;
CREATE POLICY dependency_admissions_tenant_isolation ON dependency_admissions USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence FORCE ROW LEVEL SECURITY;
CREATE POLICY evidence_tenant_isolation ON evidence USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE events FORCE ROW LEVEL SECURITY;
CREATE POLICY events_tenant_isolation ON events USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox FORCE ROW LEVEL SECURITY;
CREATE POLICY outbox_tenant_isolation ON outbox USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE command_idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE command_idempotency FORCE ROW LEVEL SECURITY;
CREATE POLICY command_idempotency_tenant_isolation ON command_idempotency USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_events_tenant_isolation ON audit_events USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid));
