-- GENERATED from schemas/objects. Do not edit.

CREATE TABLE organizations (
    organization_id uuid NOT NULL,
    slug text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (organization_id),
    UNIQUE (slug)
);

CREATE TABLE tenants (
    tenant_id uuid NOT NULL,
    organization_id uuid NOT NULL,
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
    scope_type text NOT NULL DEFAULT 'PROJECT',
    grant_scope text NOT NULL DEFAULT 'PROJECT',
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (grant_id),
    CHECK (scope_type IN ('ORGANIZATION', 'PROJECT')),
    CHECK (grant_scope IN ('ORGANIZATION', 'TENANT', 'PROJECT'))
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
    UNIQUE (project_id, slug),
    UNIQUE (mission_id, project_id, tenant_id)
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
    PRIMARY KEY (task_id),
    UNIQUE (task_id, project_id, tenant_id)
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
    assembly_tokens integer NOT NULL,
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

CREATE TABLE context_indexes (
    index_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    current_version text NOT NULL,
    embedding_model_version text NOT NULL,
    head_commit_sha text NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (index_id),
    UNIQUE (tenant_id, project_id)
);

CREATE TABLE context_chunks (
    chunk_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    index_version text NOT NULL,
    embedding_model_version text NOT NULL,
    file_path text NOT NULL,
    symbol_path text NOT NULL,
    content_hash text NOT NULL,
    start_line integer NOT NULL,
    end_line integer NOT NULL,
    language text NOT NULL,
    commit_sha text NOT NULL,
    content text NOT NULL,
    embedding jsonb NOT NULL DEFAULT '[]'::jsonb,
    current boolean NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (chunk_id),
    UNIQUE (tenant_id, project_id, index_version, file_path, symbol_path, content_hash)
);

CREATE TABLE eval_cases (
    eval_case_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    source_mission_id uuid NOT NULL,
    source_task_id uuid NOT NULL,
    source_proposal_id uuid NOT NULL,
    task_class text NOT NULL,
    is_adversarial boolean NOT NULL,
    required_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL,
    frozen_version integer,
    retired_reason text,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (eval_case_id)
);

CREATE TABLE promotion_gate_runs (
    run_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    idempotency_key text NOT NULL,
    candidate_label text NOT NULL,
    status text NOT NULL,
    corpus_size integer NOT NULL,
    task_class_count integer NOT NULL,
    adversarial_count integer NOT NULL,
    decision text,
    gate_results jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    completed_at timestamptz,
    PRIMARY KEY (run_id),
    UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE context_conflicts (
    conflict_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    package_id uuid NOT NULL,
    item_a_key text NOT NULL,
    item_a_authority_rank integer NOT NULL,
    item_b_key text NOT NULL,
    item_b_authority_rank integer NOT NULL,
    contradiction_type text NOT NULL,
    affected_success_criteria jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL,
    resolution_method text,
    resolved_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (conflict_id),
    UNIQUE (package_id, item_a_key, item_b_key)
);

CREATE TABLE context_critic_findings (
    finding_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    package_id uuid NOT NULL,
    trigger_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
    confidence numeric NOT NULL,
    action text NOT NULL,
    outcome_summary text NOT NULL,
    requires_human_review boolean NOT NULL,
    reviewed boolean NOT NULL,
    reviewed_at timestamptz,
    cost_tokens_estimate integer NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (finding_id)
);

CREATE TABLE asserted_edges (
    edge_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    edge_type text NOT NULL,
    source_key text NOT NULL,
    target_key text NOT NULL,
    asserted_by_principal uuid,
    asserted_by_mechanism text NOT NULL,
    status text NOT NULL,
    retracted_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (edge_id),
    UNIQUE (project_id, edge_type, source_key, target_key)
);

CREATE TABLE derived_edges (
    derived_edge_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    edge_type text NOT NULL,
    source_key text NOT NULL,
    target_key text NOT NULL,
    derived_at timestamptz NOT NULL,
    derived_from_commit text NOT NULL,
    deriver_version text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (derived_edge_id),
    UNIQUE (project_id, edge_type, source_key, target_key)
);

CREATE TABLE failure_attributions (
    attribution_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    task_attempt_id uuid NOT NULL,
    verification_run_id uuid NOT NULL,
    outcome text NOT NULL,
    category text NOT NULL,
    method text NOT NULL,
    rule_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
    confidence numeric NOT NULL,
    eligible_for_promotion_gating boolean NOT NULL,
    excluded_from_routing_learning boolean NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (attribution_id),
    UNIQUE (verification_run_id)
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

CREATE TABLE routing_decision_outcomes (
    outcome_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    route_decision_id uuid NOT NULL,
    task_attempt_id uuid NOT NULL,
    verification_run_id uuid NOT NULL,
    actual_verified_outcome text NOT NULL,
    verification_confidence numeric NOT NULL,
    rework_count integer NOT NULL,
    escalated boolean NOT NULL,
    human_intervention_required boolean NOT NULL,
    recovery_action text,
    failure_class text,
    elapsed_seconds numeric,
    context_package_id uuid NOT NULL,
    capability_set jsonb NOT NULL DEFAULT '[]'::jsonb,
    failure_attribution_id uuid,
    disclosed_gaps jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (outcome_id),
    UNIQUE (verification_run_id)
);

CREATE TABLE routing_simulation_runs (
    run_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    seed text NOT NULL,
    policy_version text NOT NULL,
    model_version text NOT NULL,
    scenario_classes jsonb NOT NULL DEFAULT '[]'::jsonb,
    scenario_results jsonb NOT NULL DEFAULT '[]'::jsonb,
    experience_origin text NOT NULL,
    excluded_from_routing_learning boolean NOT NULL,
    disclosed_gaps jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (run_id)
);

CREATE TABLE experience_records (
    experience_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    task_id uuid,
    route_decision_id uuid,
    task_attempt_id uuid,
    verification_run_id uuid,
    routing_simulation_run_id uuid,
    outcome_id uuid,
    experience_origin text NOT NULL,
    routing_policy_version text NOT NULL,
    candidate_set_hash text NOT NULL,
    selection_propensity numeric NOT NULL,
    prediction_vector jsonb NOT NULL DEFAULT '{}'::jsonb,
    observed_outcome_vector jsonb NOT NULL DEFAULT '{}'::jsonb,
    verification_confidence numeric NOT NULL,
    failure_attribution text NOT NULL,
    attribution_confidence numeric NOT NULL,
    holdout_partition text NOT NULL,
    promotion_evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    drift_snapshot_id uuid,
    learning_run_id uuid,
    eligible_for_routing_training boolean NOT NULL,
    eligibility_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
    down_weighted boolean NOT NULL,
    promotion_state text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (experience_id),
    UNIQUE (verification_run_id),
    UNIQUE (routing_simulation_run_id),
    CHECK ((experience_origin <> 'simulation' OR eligible_for_routing_training = false)),
    CHECK (((experience_origin = 'real' AND verification_run_id IS NOT NULL) OR (experience_origin = 'simulation' AND routing_simulation_run_id IS NOT NULL)))
);

CREATE TABLE learned_routing_policies (
    policy_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    learning_run_id uuid NOT NULL,
    fit_kind text NOT NULL,
    policy_hash text NOT NULL,
    mapping jsonb NOT NULL DEFAULT '{}'::jsonb,
    constant_policy_profile_id text NOT NULL,
    train_count integer NOT NULL,
    holdout_count integer NOT NULL,
    brier numeric,
    ece numeric,
    holdout_learner_expected numeric,
    holdout_constant_expected numeric,
    holdout_incumbent_success numeric,
    beats_constant_policy boolean NOT NULL,
    holdout_regression boolean,
    drift_within_bounds boolean,
    continued_update boolean NOT NULL,
    status text NOT NULL,
    training_experience_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    fallback_robustness_demonstrated boolean NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (policy_id),
    UNIQUE (learning_run_id),
    UNIQUE (tenant_id, project_id, policy_hash),
    CHECK (continued_update = false)
);

CREATE TABLE routing_activation_state (
    activation_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    routing_mode text NOT NULL,
    active_policy_id uuid,
    last_certified_policy_id uuid,
    last_certified_mode text NOT NULL,
    canary_fraction numeric NOT NULL DEFAULT 0.05,
    continued_update_enabled boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (activation_id),
    UNIQUE (tenant_id, project_id),
    CHECK (routing_mode IN ('deterministic', 'shadow_learning', 'canary', 'promoted_historical')),
    CHECK (last_certified_mode IN ('deterministic', 'shadow_learning', 'canary', 'promoted_historical')),
    CHECK (canary_fraction >= 0 AND canary_fraction <= 1)
);

CREATE TABLE context_activation_state (
    activation_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    context_mode text NOT NULL,
    candidate_arm text NOT NULL,
    last_certified_mode text NOT NULL,
    last_certified_arm text NOT NULL,
    last_promotion_run_id uuid,
    canary_fraction numeric NOT NULL DEFAULT 0.05,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (activation_id),
    UNIQUE (tenant_id, project_id),
    CHECK (context_mode IN ('certified_baseline', 'shadow', 'canary', 'promoted')),
    CHECK (last_certified_mode IN ('certified_baseline', 'shadow', 'canary', 'promoted')),
    CHECK (candidate_arm IN ('pull', 'push', 'semantic')),
    CHECK (last_certified_arm IN ('pull', 'push', 'semantic')),
    CHECK (canary_fraction >= 0 AND canary_fraction <= 1)
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
    UNIQUE (task_id, sequence),
    UNIQUE (attempt_id, project_id, tenant_id)
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
    UNIQUE (task_attempt_id, sequence),
    UNIQUE (run_id, project_id, tenant_id)
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
    PRIMARY KEY (artifact_id),
    UNIQUE (artifact_id, project_id, tenant_id)
);

CREATE TABLE seed_datasets (
    dataset_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    slug text NOT NULL,
    version integer NOT NULL,
    content_hash text NOT NULL,
    artifact_ref text NOT NULL,
    supersedes_dataset_id uuid,
    status text NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (dataset_id),
    UNIQUE (tenant_id, project_id, slug, version)
);

CREATE TABLE acceptance_oracles (
    oracle_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid,
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

CREATE TABLE mission_oracle_evaluations (
    evaluation_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    oracle_id uuid NOT NULL,
    workspace_id uuid NOT NULL,
    status text NOT NULL,
    task_oracle_verdict text NOT NULL,
    check_results jsonb NOT NULL DEFAULT '[]'::jsonb,
    outcome_results jsonb NOT NULL DEFAULT '[]'::jsonb,
    recovery_decision jsonb,
    learning_signal_class text NOT NULL,
    excluded_from_routing_learning boolean NOT NULL,
    disclosed_gaps jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (evaluation_id)
);

CREATE TABLE product_environments (
    product_env_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    "class" text NOT NULL,
    source_revision text NOT NULL,
    build_artifact_ref text NOT NULL,
    runtime_topology_ref jsonb NOT NULL DEFAULT '{}'::jsonb,
    datastore_ref text NOT NULL,
    seed_dataset_id uuid,
    migration_state text NOT NULL,
    migration_verification jsonb,
    base_url text,
    credentials_profile_id uuid,
    status text NOT NULL,
    ttl_expires_at timestamptz,
    failure_snapshot jsonb,
    idempotency_key text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (product_env_id),
    UNIQUE (tenant_id, project_id, idempotency_key)
);

CREATE TABLE domain_invariants (
    invariant_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    name text NOT NULL,
    description text NOT NULL,
    predicate jsonb NOT NULL,
    financial_state boolean NOT NULL,
    required_fixture_class text NOT NULL,
    product_env_class text NOT NULL,
    definition_version text NOT NULL,
    status text NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (invariant_id),
    UNIQUE (project_id, name, definition_version)
);

CREATE TABLE invariant_evaluations (
    evaluation_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    invariant_id uuid NOT NULL,
    definition_version text NOT NULL,
    product_env_id uuid NOT NULL,
    datastore_ref text,
    sequence integer NOT NULL,
    status text NOT NULL,
    violations jsonb NOT NULL DEFAULT '[]'::jsonb,
    rows_checked integer NOT NULL,
    financial_state boolean NOT NULL,
    repair_task_ref text,
    seed_dataset_id uuid,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (evaluation_id),
    UNIQUE (tenant_id, project_id, invariant_id, product_env_id, sequence)
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
    UNIQUE (worker_run_id, sequence),
    UNIQUE (verification_run_id, project_id, tenant_id)
);

CREATE TABLE plan_drafts (
    draft_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    origin text NOT NULL,
    adapter_ref text,
    origin_policy_version text NOT NULL,
    nodes jsonb NOT NULL DEFAULT '[]'::jsonb,
    edges jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL,
    refusals jsonb NOT NULL DEFAULT '[]'::jsonb,
    promoted_graph_id uuid,
    provenance_key text NOT NULL,
    created_by_principal uuid NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (draft_id),
    UNIQUE (tenant_id, project_id, provenance_key)
);

CREATE TABLE mission_templates (
    template_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    template_key text NOT NULL,
    template_version text NOT NULL,
    description text NOT NULL,
    nodes jsonb NOT NULL DEFAULT '[]'::jsonb,
    edges jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL,
    planner_policy_version text NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (template_id),
    UNIQUE (project_id, template_key, template_version)
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

CREATE TABLE tenant_overhead_budget_settings (
    tenant_id uuid NOT NULL,
    hard_cap_overhead_token_share numeric NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id)
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

CREATE TABLE approvals (
    approval_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid,
    approval_type text NOT NULL,
    scope_hash text NOT NULL,
    requested_by uuid NOT NULL,
    required_role text NOT NULL,
    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    suggested_decision text,
    status text NOT NULL,
    decided_by uuid,
    decided_at timestamptz,
    expires_at timestamptz,
    rationale text,
    standing_id uuid,
    edr_id uuid,
    human_minutes numeric NOT NULL,
    command_id uuid NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (approval_id)
);

CREATE TABLE standing_approvals (
    standing_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    approval_types jsonb NOT NULL DEFAULT '[]'::jsonb,
    blast_radius_ceiling text NOT NULL,
    risk_ceiling text NOT NULL,
    cost_ceiling numeric NOT NULL,
    task_count_ceiling integer NOT NULL,
    path_scope jsonb NOT NULL DEFAULT '[]'::jsonb,
    forbidden_operations jsonb NOT NULL DEFAULT '[]'::jsonb,
    valid_from timestamptz NOT NULL,
    valid_until timestamptz NOT NULL,
    revocable_immediately boolean NOT NULL,
    granted_by uuid NOT NULL,
    rationale text NOT NULL,
    status text NOT NULL,
    task_count_used integer NOT NULL,
    cost_used numeric NOT NULL,
    revoked_at timestamptz,
    command_id uuid NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (standing_id)
);

CREATE TABLE control_plane_overhead_tasks (
    overhead_task_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    task_attempt_id uuid NOT NULL,
    worker_run_id uuid NOT NULL,
    execution_plan_id uuid NOT NULL,
    context_package_id uuid NOT NULL,
    environment_id uuid NOT NULL,
    estimated_effort text NOT NULL,
    context_assembly_tokens integer NOT NULL,
    context_critic_tokens integer NOT NULL,
    routing_tokens integer NOT NULL,
    route_critic_tokens integer NOT NULL,
    planning_tokens integer NOT NULL,
    judge_tokens integer NOT NULL,
    overhead_tokens integer NOT NULL,
    environment_provisioning_ms integer NOT NULL,
    queue_wait_seconds numeric NOT NULL,
    overhead_seconds_before_first_worker_action_seconds numeric NOT NULL,
    context_critic_invoked boolean NOT NULL,
    route_critic_invoked boolean NOT NULL,
    workload_class text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (overhead_task_id),
    UNIQUE (worker_run_id)
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

CREATE TABLE attention_items (
    attention_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    kind text NOT NULL,
    summary text NOT NULL,
    status text NOT NULL,
    approval_id uuid,
    standing_id uuid,
    sla_due_at timestamptz NOT NULL,
    opened_at timestamptz NOT NULL,
    acknowledged_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (attention_id)
);

CREATE TABLE client_sessions (
    session_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    principal_id uuid NOT NULL,
    client_type text NOT NULL,
    device_id uuid,
    protocol_version text NOT NULL,
    scopes jsonb NOT NULL DEFAULT '[]'::jsonb,
    connected_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    subscriptions jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (session_id)
);

CREATE TABLE workload_class_cost_metrics (
    metric_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    workload_class text NOT NULL,
    verified_success_count integer NOT NULL,
    total_overhead_tokens integer NOT NULL,
    cost_tokens_per_verified_success numeric NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (metric_id),
    UNIQUE (tenant_id, project_id, workload_class)
);

CREATE TABLE donor_artifacts (
    donor_artifact_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    source_uri text NOT NULL,
    content_hash text NOT NULL,
    source_class text NOT NULL,
    authority_rank integer NOT NULL,
    media_kind text NOT NULL,
    status text NOT NULL,
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    feature_dna_id uuid,
    injection_findings jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (donor_artifact_id),
    UNIQUE (project_id, content_hash)
);

CREATE TABLE feature_dna (
    feature_dna_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    donor_artifact_id uuid NOT NULL,
    title text NOT NULL,
    body jsonb NOT NULL DEFAULT '{}'::jsonb,
    donor_sources jsonb NOT NULL DEFAULT '[]'::jsonb,
    dna_hash text NOT NULL,
    taint_tags jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (feature_dna_id),
    UNIQUE (project_id, dna_hash)
);

CREATE TABLE captured_provider_credentials (
    capture_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    provider_id text NOT NULL,
    domain text,
    secret_hash text NOT NULL,
    fingerprint text NOT NULL,
    last4 text NOT NULL,
    status text NOT NULL,
    supersedes_capture_id uuid,
    superseded_by_capture_id uuid,
    captured_by text NOT NULL,
    captured_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (capture_id)
);

CREATE TABLE donor_taints (
    donor_taint_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    donor_artifact_id uuid NOT NULL,
    subject_kind text NOT NULL,
    subject_id uuid NOT NULL,
    source_class text NOT NULL,
    licence_class text NOT NULL,
    taint_tags jsonb NOT NULL DEFAULT '[]'::jsonb,
    source_uri text NOT NULL,
    signed_reuse_decision_id uuid,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (donor_taint_id),
    UNIQUE (project_id, subject_kind, subject_id, donor_artifact_id)
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

CREATE TABLE frontend_contracts (
    contract_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    contract_version integer NOT NULL,
    content_hash text NOT NULL,
    status text NOT NULL,
    obligations jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (contract_id),
    UNIQUE (tenant_id, project_id, contract_version),
    CHECK (contract_version >= 1),
    CHECK (status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED'))
);

CREATE TABLE pxg_nodes (
    node_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    pxg_key text NOT NULL,
    node_kind text NOT NULL,
    title text NOT NULL,
    parent_key text,
    pxg_revision integer NOT NULL,
    source_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (node_id),
    UNIQUE (tenant_id, project_id, pxg_key),
    CHECK (pxg_revision >= 1),
    CHECK (node_kind IN ('journey', 'screen', 'region', 'component', 'interaction', 'state', 'data_binding', 'navigation', 'responsive_state', 'accessibility_contract'))
);

CREATE TABLE pxg_edges (
    edge_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    from_key text NOT NULL,
    to_key text NOT NULL,
    edge_kind text NOT NULL,
    pxg_revision integer NOT NULL,
    attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (edge_id),
    UNIQUE (tenant_id, project_id, from_key, edge_kind, to_key),
    CHECK (edge_kind IN ('navigates_to', 'triggers', 'binds_data', 'renders_state', 'satisfies', 'derived_from', 'depends_on', 'variant_of')),
    CHECK (pxg_revision >= 1)
);

CREATE TABLE frontend_coverage_snapshots (
    snapshot_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    contract_id uuid NOT NULL,
    contract_version integer NOT NULL,
    pxg_revision integer NOT NULL,
    summary_state text NOT NULL,
    weighted_percent numeric,
    dimensions jsonb NOT NULL DEFAULT '[]'::jsonb,
    findings jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (snapshot_id),
    CHECK ((weighted_percent IS NULL OR (weighted_percent >= 0 AND weighted_percent <= 100))),
    CHECK (summary_state IN ('UNASSESSED', 'PARTIAL', 'ASSESSED', 'BLOCKED')),
    CHECK ((weighted_percent IS NULL OR summary_state = 'ASSESSED'))
);

CREATE TABLE frontend_locks (
    lock_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    lock_kind text NOT NULL,
    scope_key text NOT NULL,
    status text NOT NULL,
    reason text NOT NULL,
    created_by uuid NOT NULL,
    released_by uuid,
    released_at timestamptz,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (lock_id),
    CHECK (lock_kind IN ('GLOBAL_DESIGN', 'SCREEN', 'SECTION', 'COMPONENT', 'STYLE', 'STRUCTURE', 'BEHAVIOUR', 'CONTENT', 'TOKEN')),
    CHECK (status IN ('ACTIVE', 'RELEASED'))
);

CREATE TABLE frontend_candidates (
    candidate_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    workspace_id uuid,
    title text NOT NULL,
    state text NOT NULL,
    origin text NOT NULL,
    base_pxg_revision integer NOT NULL,
    base_contract_version integer,
    scope_keys jsonb NOT NULL DEFAULT '[]'::jsonb,
    verification_run_id uuid,
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    state_detail text,
    superseded_by uuid,
    promoted_at timestamptz,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (candidate_id),
    CHECK (state IN ('REQUESTED', 'GENERATING', 'GENERATED', 'MATERIALIZING', 'RENDERING', 'READY', 'EDITING', 'DIRTY', 'VERIFYING', 'FAILED', 'REPAIRABLE', 'REPAIRING', 'VERIFIED', 'REJECTED', 'BLOCKED', 'PROMOTABLE', 'PROMOTING', 'PROMOTED', 'SUPERSEDED', 'ERRORED')),
    CHECK (origin IN ('DESIGN_ARTIFACT', 'DIRECT_EDIT', 'TEMPLATE_BLEND', 'SOURCE_IMPORT', 'AGENT_PACKET', 'REPAIR_CYCLE')),
    CHECK (base_pxg_revision >= 0)
);

CREATE TABLE frontend_mutations (
    mutation_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    candidate_id uuid NOT NULL,
    sequence integer NOT NULL,
    operation text NOT NULL,
    target_key text NOT NULL,
    origin text NOT NULL,
    status text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    inverse jsonb NOT NULL DEFAULT '{}'::jsonb,
    preconditions jsonb NOT NULL,
    refusal_code text,
    refusal_detail text,
    reverted_by uuid,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (mutation_id),
    UNIQUE (candidate_id, sequence),
    CHECK (operation IN ('ADD', 'REMOVE', 'MOVE', 'REORDER', 'REPLACE', 'RESTYLE', 'SET_PROPERTY', 'SET_BEHAVIOUR', 'SET_RESPONSIVE')),
    CHECK (status IN ('PLANNED', 'APPLIED', 'REVERTED', 'REFUSED')),
    CHECK (origin IN ('INSPECTOR', 'CHAT', 'DIRECT_MANIPULATION', 'DESIGN_PROVIDER', 'TEMPLATE', 'SOURCE_IMPORT', 'AGENT', 'KEYBOARD', 'REPAIR')),
    CHECK ((status <> 'REFUSED' OR refusal_code IS NOT NULL)),
    CHECK (sequence >= 1)
);

CREATE TABLE design_sessions (
    session_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    conversation_id uuid,
    candidate_id uuid,
    status text NOT NULL,
    scope_keys jsonb NOT NULL DEFAULT '[]'::jsonb,
    design_system_hash text NOT NULL,
    base_pxg_revision integer NOT NULL,
    context_manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (session_id),
    CHECK (status IN ('OPEN', 'CLOSED', 'ABANDONED'))
);

CREATE TABLE design_artifacts (
    artifact_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    session_id uuid NOT NULL,
    direction_label text NOT NULL,
    revision integer NOT NULL,
    status text NOT NULL,
    provider_id text NOT NULL,
    content_hash text NOT NULL,
    content jsonb NOT NULL DEFAULT '{}'::jsonb,
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    quarantine_reason text,
    candidate_id uuid,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (artifact_id),
    UNIQUE (session_id, direction_label, revision),
    CHECK (status IN ('GENERATED', 'QUARANTINED', 'SELECTED', 'TRIED_LIVE', 'DISCARDED')),
    CHECK (revision >= 1)
);

CREATE TABLE frontend_conversations (
    conversation_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    active_candidate_id uuid,
    design_session_id uuid,
    selected_node_keys jsonb NOT NULL DEFAULT '[]'::jsonb,
    viewport text NOT NULL,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (conversation_id)
);

CREATE TABLE frontend_conversation_turns (
    turn_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    sequence integer NOT NULL,
    role text NOT NULL,
    text text NOT NULL,
    intent text NOT NULL,
    outcome text NOT NULL,
    refusal_code text,
    refusal_detail text,
    resolved_context jsonb NOT NULL DEFAULT '{}'::jsonb,
    produced_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (turn_id),
    UNIQUE (conversation_id, sequence),
    CHECK (sequence >= 1),
    CHECK (role IN ('user', 'studio')),
    CHECK (outcome IN ('ROUTED', 'REFUSED', 'ANSWERED'))
);

CREATE TABLE frontend_preview_sessions (
    preview_session_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    candidate_id uuid NOT NULL,
    workspace_id uuid,
    screen_key text NOT NULL,
    state text NOT NULL,
    viewport text NOT NULL,
    route text,
    candidate_pxg_revision integer NOT NULL,
    source_revision text,
    document_path text,
    content_hash text,
    state_detail text,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    source_path text,
    PRIMARY KEY (preview_session_id),
    CHECK (state IN ('BUILDING', 'LOADING', 'LIVE', 'STALE', 'RUNTIME_ERROR', 'RENDER_ERROR', 'UNAVAILABLE', 'STOPPED')),
    CHECK (candidate_pxg_revision >= 0)
);

ALTER TABLE tenants ADD CONSTRAINT tenants_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES organizations (organization_id);

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

ALTER TABLE context_indexes ADD CONSTRAINT context_indexes_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE context_indexes ADD CONSTRAINT context_indexes_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE context_chunks ADD CONSTRAINT context_chunks_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE context_chunks ADD CONSTRAINT context_chunks_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE eval_cases ADD CONSTRAINT eval_cases_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE eval_cases ADD CONSTRAINT eval_cases_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE eval_cases ADD CONSTRAINT eval_cases_source_mission_id_fkey FOREIGN KEY (source_mission_id) REFERENCES missions (mission_id);
ALTER TABLE eval_cases ADD CONSTRAINT eval_cases_source_task_id_fkey FOREIGN KEY (source_task_id) REFERENCES tasks (task_id);
ALTER TABLE eval_cases ADD CONSTRAINT eval_cases_source_proposal_id_fkey FOREIGN KEY (source_proposal_id) REFERENCES integration_proposals (proposal_id);

ALTER TABLE promotion_gate_runs ADD CONSTRAINT promotion_gate_runs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE promotion_gate_runs ADD CONSTRAINT promotion_gate_runs_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE context_conflicts ADD CONSTRAINT context_conflicts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE context_conflicts ADD CONSTRAINT context_conflicts_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE context_conflicts ADD CONSTRAINT context_conflicts_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE context_conflicts ADD CONSTRAINT context_conflicts_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE context_conflicts ADD CONSTRAINT context_conflicts_package_id_fkey FOREIGN KEY (package_id) REFERENCES context_packages (package_id);

ALTER TABLE context_critic_findings ADD CONSTRAINT context_critic_findings_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE context_critic_findings ADD CONSTRAINT context_critic_findings_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE context_critic_findings ADD CONSTRAINT context_critic_findings_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE context_critic_findings ADD CONSTRAINT context_critic_findings_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE context_critic_findings ADD CONSTRAINT context_critic_findings_package_id_fkey FOREIGN KEY (package_id) REFERENCES context_packages (package_id);

ALTER TABLE asserted_edges ADD CONSTRAINT asserted_edges_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE asserted_edges ADD CONSTRAINT asserted_edges_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE derived_edges ADD CONSTRAINT derived_edges_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE derived_edges ADD CONSTRAINT derived_edges_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE failure_attributions ADD CONSTRAINT failure_attributions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE failure_attributions ADD CONSTRAINT failure_attributions_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE failure_attributions ADD CONSTRAINT failure_attributions_verification_run_id_fkey FOREIGN KEY (verification_run_id) REFERENCES verification_runs (verification_run_id);

ALTER TABLE route_decisions ADD CONSTRAINT route_decisions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE route_decisions ADD CONSTRAINT route_decisions_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE route_decisions ADD CONSTRAINT route_decisions_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE route_decisions ADD CONSTRAINT route_decisions_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);

ALTER TABLE routing_decision_outcomes ADD CONSTRAINT routing_decision_outcomes_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE routing_decision_outcomes ADD CONSTRAINT routing_decision_outcomes_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE routing_decision_outcomes ADD CONSTRAINT routing_decision_outcomes_route_decision_id_fkey FOREIGN KEY (route_decision_id) REFERENCES route_decisions (decision_id);
ALTER TABLE routing_decision_outcomes ADD CONSTRAINT routing_decision_outcomes_verification_run_id_fkey FOREIGN KEY (verification_run_id) REFERENCES verification_runs (verification_run_id);
ALTER TABLE routing_decision_outcomes ADD CONSTRAINT routing_decision_outcomes_failure_attribution_id_fkey FOREIGN KEY (failure_attribution_id) REFERENCES failure_attributions (attribution_id);

ALTER TABLE routing_simulation_runs ADD CONSTRAINT routing_simulation_runs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE routing_simulation_runs ADD CONSTRAINT routing_simulation_runs_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE experience_records ADD CONSTRAINT experience_records_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE experience_records ADD CONSTRAINT experience_records_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE experience_records ADD CONSTRAINT experience_records_route_decision_id_fkey FOREIGN KEY (route_decision_id) REFERENCES route_decisions (decision_id);
ALTER TABLE experience_records ADD CONSTRAINT experience_records_verification_run_id_fkey FOREIGN KEY (verification_run_id) REFERENCES verification_runs (verification_run_id);
ALTER TABLE experience_records ADD CONSTRAINT experience_records_routing_simulation_run_id_fkey FOREIGN KEY (routing_simulation_run_id) REFERENCES routing_simulation_runs (run_id);
ALTER TABLE experience_records ADD CONSTRAINT experience_records_outcome_id_fkey FOREIGN KEY (outcome_id) REFERENCES routing_decision_outcomes (outcome_id);

ALTER TABLE learned_routing_policies ADD CONSTRAINT learned_routing_policies_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE learned_routing_policies ADD CONSTRAINT learned_routing_policies_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE routing_activation_state ADD CONSTRAINT routing_activation_state_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE routing_activation_state ADD CONSTRAINT routing_activation_state_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE routing_activation_state ADD CONSTRAINT routing_activation_state_active_policy_id_fkey FOREIGN KEY (active_policy_id) REFERENCES learned_routing_policies (policy_id);
ALTER TABLE routing_activation_state ADD CONSTRAINT routing_activation_state_last_certified_policy_id_fkey FOREIGN KEY (last_certified_policy_id) REFERENCES learned_routing_policies (policy_id);

ALTER TABLE context_activation_state ADD CONSTRAINT context_activation_state_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE context_activation_state ADD CONSTRAINT context_activation_state_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE context_activation_state ADD CONSTRAINT context_activation_state_last_promotion_run_id_fkey FOREIGN KEY (last_promotion_run_id) REFERENCES promotion_gate_runs (run_id);

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

ALTER TABLE task_attempts ADD CONSTRAINT task_attempts_mission_scope_fkey FOREIGN KEY (mission_id, project_id, tenant_id) REFERENCES missions (mission_id, project_id, tenant_id);
ALTER TABLE task_attempts ADD CONSTRAINT task_attempts_task_scope_fkey FOREIGN KEY (task_id, project_id, tenant_id) REFERENCES tasks (task_id, project_id, tenant_id);
ALTER TABLE task_attempts ADD CONSTRAINT task_attempts_execution_plan_id_fkey FOREIGN KEY (execution_plan_id) REFERENCES execution_plans (plan_id);
ALTER TABLE task_attempts ADD CONSTRAINT task_attempts_retry_of_fkey FOREIGN KEY (retry_of) REFERENCES task_attempts (attempt_id);

ALTER TABLE worker_runs ADD CONSTRAINT worker_runs_task_attempt_scope_fkey FOREIGN KEY (task_attempt_id, project_id, tenant_id) REFERENCES task_attempts (attempt_id, project_id, tenant_id);
ALTER TABLE worker_runs ADD CONSTRAINT worker_runs_mission_scope_fkey FOREIGN KEY (mission_id, project_id, tenant_id) REFERENCES missions (mission_id, project_id, tenant_id);
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

ALTER TABLE artifacts ADD CONSTRAINT artifacts_mission_scope_fkey FOREIGN KEY (mission_id, project_id, tenant_id) REFERENCES missions (mission_id, project_id, tenant_id);

ALTER TABLE seed_datasets ADD CONSTRAINT seed_datasets_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE seed_datasets ADD CONSTRAINT seed_datasets_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE seed_datasets ADD CONSTRAINT seed_datasets_supersedes_dataset_id_fkey FOREIGN KEY (supersedes_dataset_id) REFERENCES seed_datasets (dataset_id);

ALTER TABLE acceptance_oracles ADD CONSTRAINT acceptance_oracles_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE acceptance_oracles ADD CONSTRAINT acceptance_oracles_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE acceptance_oracles ADD CONSTRAINT acceptance_oracles_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE acceptance_oracles ADD CONSTRAINT acceptance_oracles_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);

ALTER TABLE mission_oracle_evaluations ADD CONSTRAINT mission_oracle_evaluations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE mission_oracle_evaluations ADD CONSTRAINT mission_oracle_evaluations_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE mission_oracle_evaluations ADD CONSTRAINT mission_oracle_evaluations_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE mission_oracle_evaluations ADD CONSTRAINT mission_oracle_evaluations_oracle_id_fkey FOREIGN KEY (oracle_id) REFERENCES acceptance_oracles (oracle_id);
ALTER TABLE mission_oracle_evaluations ADD CONSTRAINT mission_oracle_evaluations_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces (workspace_id);

ALTER TABLE product_environments ADD CONSTRAINT product_environments_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE product_environments ADD CONSTRAINT product_environments_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE product_environments ADD CONSTRAINT product_environments_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE product_environments ADD CONSTRAINT product_environments_seed_dataset_id_fkey FOREIGN KEY (seed_dataset_id) REFERENCES seed_datasets (dataset_id);
ALTER TABLE product_environments ADD CONSTRAINT product_environments_credentials_profile_id_fkey FOREIGN KEY (credentials_profile_id) REFERENCES credential_handles (handle_id);

ALTER TABLE domain_invariants ADD CONSTRAINT domain_invariants_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE domain_invariants ADD CONSTRAINT domain_invariants_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE invariant_evaluations ADD CONSTRAINT invariant_evaluations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE invariant_evaluations ADD CONSTRAINT invariant_evaluations_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE invariant_evaluations ADD CONSTRAINT invariant_evaluations_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE invariant_evaluations ADD CONSTRAINT invariant_evaluations_invariant_id_fkey FOREIGN KEY (invariant_id) REFERENCES domain_invariants (invariant_id);
ALTER TABLE invariant_evaluations ADD CONSTRAINT invariant_evaluations_product_env_id_fkey FOREIGN KEY (product_env_id) REFERENCES product_environments (product_env_id);

ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_mission_scope_fkey FOREIGN KEY (mission_id, project_id, tenant_id) REFERENCES missions (mission_id, project_id, tenant_id);
ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_task_scope_fkey FOREIGN KEY (task_id, project_id, tenant_id) REFERENCES tasks (task_id, project_id, tenant_id);
ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_attempt_scope_fkey FOREIGN KEY (task_attempt_id, project_id, tenant_id) REFERENCES task_attempts (attempt_id, project_id, tenant_id);
ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_worker_run_scope_fkey FOREIGN KEY (worker_run_id, project_id, tenant_id) REFERENCES worker_runs (run_id, project_id, tenant_id);
ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces (workspace_id);
ALTER TABLE verification_runs ADD CONSTRAINT verification_runs_oracle_id_fkey FOREIGN KEY (oracle_id) REFERENCES acceptance_oracles (oracle_id);

ALTER TABLE plan_drafts ADD CONSTRAINT plan_drafts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE plan_drafts ADD CONSTRAINT plan_drafts_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE plan_drafts ADD CONSTRAINT plan_drafts_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);

ALTER TABLE mission_templates ADD CONSTRAINT mission_templates_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE mission_templates ADD CONSTRAINT mission_templates_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_task_attempt_id_fkey FOREIGN KEY (task_attempt_id) REFERENCES task_attempts (attempt_id);
ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_scope_lease_id_fkey FOREIGN KEY (scope_lease_id) REFERENCES write_scope_leases (lease_id);
ALTER TABLE integration_proposals ADD CONSTRAINT integration_proposals_verification_ref_fkey FOREIGN KEY (pre_integration_verification_ref) REFERENCES verification_runs (verification_run_id);

ALTER TABLE tenant_overhead_budget_settings ADD CONSTRAINT tenant_overhead_budget_settings_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);

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

ALTER TABLE approvals ADD CONSTRAINT approvals_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE approvals ADD CONSTRAINT approvals_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE approvals ADD CONSTRAINT approvals_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE approvals ADD CONSTRAINT approvals_command_id_fkey FOREIGN KEY (command_id) REFERENCES command_idempotency (command_id);

ALTER TABLE standing_approvals ADD CONSTRAINT standing_approvals_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE standing_approvals ADD CONSTRAINT standing_approvals_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE standing_approvals ADD CONSTRAINT standing_approvals_command_id_fkey FOREIGN KEY (command_id) REFERENCES command_idempotency (command_id);

ALTER TABLE control_plane_overhead_tasks ADD CONSTRAINT control_plane_overhead_tasks_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE control_plane_overhead_tasks ADD CONSTRAINT control_plane_overhead_tasks_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE control_plane_overhead_tasks ADD CONSTRAINT control_plane_overhead_tasks_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE control_plane_overhead_tasks ADD CONSTRAINT control_plane_overhead_tasks_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE control_plane_overhead_tasks ADD CONSTRAINT control_plane_overhead_tasks_task_attempt_id_fkey FOREIGN KEY (task_attempt_id) REFERENCES task_attempts (attempt_id);
ALTER TABLE control_plane_overhead_tasks ADD CONSTRAINT control_plane_overhead_tasks_worker_run_id_fkey FOREIGN KEY (worker_run_id) REFERENCES worker_runs (run_id);
ALTER TABLE control_plane_overhead_tasks ADD CONSTRAINT control_plane_overhead_tasks_execution_plan_id_fkey FOREIGN KEY (execution_plan_id) REFERENCES execution_plans (plan_id);
ALTER TABLE control_plane_overhead_tasks ADD CONSTRAINT control_plane_overhead_tasks_context_package_id_fkey FOREIGN KEY (context_package_id) REFERENCES context_packages (package_id);
ALTER TABLE control_plane_overhead_tasks ADD CONSTRAINT control_plane_overhead_tasks_environment_id_fkey FOREIGN KEY (environment_id) REFERENCES execution_environments (environment_id);

ALTER TABLE evidence ADD CONSTRAINT evidence_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE evidence ADD CONSTRAINT evidence_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE evidence ADD CONSTRAINT evidence_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE evidence ADD CONSTRAINT evidence_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);
ALTER TABLE evidence ADD CONSTRAINT evidence_verification_run_id_fkey FOREIGN KEY (verification_run_id) REFERENCES verification_runs (verification_run_id);

ALTER TABLE attention_items ADD CONSTRAINT attention_items_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE attention_items ADD CONSTRAINT attention_items_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE attention_items ADD CONSTRAINT attention_items_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);

ALTER TABLE client_sessions ADD CONSTRAINT client_sessions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE client_sessions ADD CONSTRAINT client_sessions_principal_id_fkey FOREIGN KEY (principal_id) REFERENCES principals (principal_id);

ALTER TABLE workload_class_cost_metrics ADD CONSTRAINT workload_class_cost_metrics_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE workload_class_cost_metrics ADD CONSTRAINT workload_class_cost_metrics_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE donor_artifacts ADD CONSTRAINT donor_artifacts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE donor_artifacts ADD CONSTRAINT donor_artifacts_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE donor_artifacts ADD CONSTRAINT donor_artifacts_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);

ALTER TABLE feature_dna ADD CONSTRAINT feature_dna_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE feature_dna ADD CONSTRAINT feature_dna_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE feature_dna ADD CONSTRAINT feature_dna_donor_artifact_id_fkey FOREIGN KEY (donor_artifact_id) REFERENCES donor_artifacts (donor_artifact_id);

ALTER TABLE captured_provider_credentials ADD CONSTRAINT captured_provider_credentials_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE captured_provider_credentials ADD CONSTRAINT captured_provider_credentials_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE captured_provider_credentials ADD CONSTRAINT captured_provider_credentials_supersedes_capture_id_fkey FOREIGN KEY (supersedes_capture_id) REFERENCES captured_provider_credentials (capture_id);
ALTER TABLE captured_provider_credentials ADD CONSTRAINT captured_provider_credentials_superseded_by_capture_id_fkey FOREIGN KEY (superseded_by_capture_id) REFERENCES captured_provider_credentials (capture_id);

ALTER TABLE donor_taints ADD CONSTRAINT donor_taints_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE donor_taints ADD CONSTRAINT donor_taints_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE donor_taints ADD CONSTRAINT donor_taints_donor_artifact_id_fkey FOREIGN KEY (donor_artifact_id) REFERENCES donor_artifacts (donor_artifact_id);

ALTER TABLE events ADD CONSTRAINT events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE events ADD CONSTRAINT events_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE outbox ADD CONSTRAINT outbox_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE outbox ADD CONSTRAINT outbox_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE command_idempotency ADD CONSTRAINT command_idempotency_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE command_idempotency ADD CONSTRAINT command_idempotency_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE audit_events ADD CONSTRAINT audit_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE audit_events ADD CONSTRAINT audit_events_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE frontend_contracts ADD CONSTRAINT frontend_contracts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE frontend_contracts ADD CONSTRAINT frontend_contracts_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE frontend_contracts ADD CONSTRAINT frontend_contracts_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);

ALTER TABLE pxg_nodes ADD CONSTRAINT pxg_nodes_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE pxg_nodes ADD CONSTRAINT pxg_nodes_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE pxg_edges ADD CONSTRAINT pxg_edges_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE pxg_edges ADD CONSTRAINT pxg_edges_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE frontend_coverage_snapshots ADD CONSTRAINT frontend_coverage_snapshots_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE frontend_coverage_snapshots ADD CONSTRAINT frontend_coverage_snapshots_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE frontend_coverage_snapshots ADD CONSTRAINT frontend_coverage_snapshots_contract_id_fkey FOREIGN KEY (contract_id) REFERENCES frontend_contracts (contract_id);

ALTER TABLE frontend_locks ADD CONSTRAINT frontend_locks_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE frontend_locks ADD CONSTRAINT frontend_locks_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);

ALTER TABLE frontend_candidates ADD CONSTRAINT frontend_candidates_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE frontend_candidates ADD CONSTRAINT frontend_candidates_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE frontend_candidates ADD CONSTRAINT frontend_candidates_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE frontend_candidates ADD CONSTRAINT frontend_candidates_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces (workspace_id);

ALTER TABLE frontend_mutations ADD CONSTRAINT frontend_mutations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE frontend_mutations ADD CONSTRAINT frontend_mutations_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE frontend_mutations ADD CONSTRAINT frontend_mutations_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES frontend_candidates (candidate_id);

ALTER TABLE design_sessions ADD CONSTRAINT design_sessions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE design_sessions ADD CONSTRAINT design_sessions_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE design_sessions ADD CONSTRAINT design_sessions_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);

ALTER TABLE design_artifacts ADD CONSTRAINT design_artifacts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE design_artifacts ADD CONSTRAINT design_artifacts_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE design_artifacts ADD CONSTRAINT design_artifacts_session_id_fkey FOREIGN KEY (session_id) REFERENCES design_sessions (session_id);

ALTER TABLE frontend_conversations ADD CONSTRAINT frontend_conversations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE frontend_conversations ADD CONSTRAINT frontend_conversations_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE frontend_conversations ADD CONSTRAINT frontend_conversations_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);

ALTER TABLE frontend_conversation_turns ADD CONSTRAINT frontend_conversation_turns_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE frontend_conversation_turns ADD CONSTRAINT frontend_conversation_turns_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE frontend_conversation_turns ADD CONSTRAINT frontend_conversation_turns_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES frontend_conversations (conversation_id);

ALTER TABLE frontend_preview_sessions ADD CONSTRAINT frontend_preview_sessions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);
ALTER TABLE frontend_preview_sessions ADD CONSTRAINT frontend_preview_sessions_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);
ALTER TABLE frontend_preview_sessions ADD CONSTRAINT frontend_preview_sessions_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);
ALTER TABLE frontend_preview_sessions ADD CONSTRAINT frontend_preview_sessions_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES frontend_candidates (candidate_id);
ALTER TABLE frontend_preview_sessions ADD CONSTRAINT frontend_preview_sessions_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces (workspace_id);

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
CREATE POLICY organizations_tenant_isolation ON organizations USING (organization_id = CAST(current_setting('dde.organization_id', true) AS uuid)) WITH CHECK (organization_id = CAST(current_setting('dde.organization_id', true) AS uuid));

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

ALTER TABLE context_indexes ENABLE ROW LEVEL SECURITY;
ALTER TABLE context_indexes FORCE ROW LEVEL SECURITY;
CREATE POLICY context_indexes_tenant_isolation ON context_indexes USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE context_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE context_chunks FORCE ROW LEVEL SECURITY;
CREATE POLICY context_chunks_tenant_isolation ON context_chunks USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE eval_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE eval_cases FORCE ROW LEVEL SECURITY;
CREATE POLICY eval_cases_tenant_isolation ON eval_cases USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE promotion_gate_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE promotion_gate_runs FORCE ROW LEVEL SECURITY;
CREATE POLICY promotion_gate_runs_tenant_isolation ON promotion_gate_runs USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE context_conflicts ENABLE ROW LEVEL SECURITY;
ALTER TABLE context_conflicts FORCE ROW LEVEL SECURITY;
CREATE POLICY context_conflicts_tenant_isolation ON context_conflicts USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE context_critic_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE context_critic_findings FORCE ROW LEVEL SECURITY;
CREATE POLICY context_critic_findings_tenant_isolation ON context_critic_findings USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE asserted_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE asserted_edges FORCE ROW LEVEL SECURITY;
CREATE POLICY asserted_edges_tenant_isolation ON asserted_edges USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE derived_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE derived_edges FORCE ROW LEVEL SECURITY;
CREATE POLICY derived_edges_tenant_isolation ON derived_edges USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE failure_attributions ENABLE ROW LEVEL SECURITY;
ALTER TABLE failure_attributions FORCE ROW LEVEL SECURITY;
CREATE POLICY failure_attributions_tenant_isolation ON failure_attributions USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE route_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE route_decisions FORCE ROW LEVEL SECURITY;
CREATE POLICY route_decisions_tenant_isolation ON route_decisions USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE routing_decision_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE routing_decision_outcomes FORCE ROW LEVEL SECURITY;
CREATE POLICY routing_decision_outcomes_tenant_isolation ON routing_decision_outcomes USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE routing_simulation_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE routing_simulation_runs FORCE ROW LEVEL SECURITY;
CREATE POLICY routing_simulation_runs_tenant_isolation ON routing_simulation_runs USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE experience_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE experience_records FORCE ROW LEVEL SECURITY;
CREATE POLICY experience_records_tenant_isolation ON experience_records USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE learned_routing_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE learned_routing_policies FORCE ROW LEVEL SECURITY;
CREATE POLICY learned_routing_policies_tenant_isolation ON learned_routing_policies USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE routing_activation_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE routing_activation_state FORCE ROW LEVEL SECURITY;
CREATE POLICY routing_activation_state_tenant_isolation ON routing_activation_state USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE context_activation_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE context_activation_state FORCE ROW LEVEL SECURITY;
CREATE POLICY context_activation_state_tenant_isolation ON context_activation_state USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

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

ALTER TABLE seed_datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE seed_datasets FORCE ROW LEVEL SECURITY;
CREATE POLICY seed_datasets_tenant_isolation ON seed_datasets USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE acceptance_oracles ENABLE ROW LEVEL SECURITY;
ALTER TABLE acceptance_oracles FORCE ROW LEVEL SECURITY;
CREATE POLICY acceptance_oracles_tenant_isolation ON acceptance_oracles USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE mission_oracle_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE mission_oracle_evaluations FORCE ROW LEVEL SECURITY;
CREATE POLICY mission_oracle_evaluations_tenant_isolation ON mission_oracle_evaluations USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE product_environments ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_environments FORCE ROW LEVEL SECURITY;
CREATE POLICY product_environments_tenant_isolation ON product_environments USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE domain_invariants ENABLE ROW LEVEL SECURITY;
ALTER TABLE domain_invariants FORCE ROW LEVEL SECURITY;
CREATE POLICY domain_invariants_tenant_isolation ON domain_invariants USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE invariant_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE invariant_evaluations FORCE ROW LEVEL SECURITY;
CREATE POLICY invariant_evaluations_tenant_isolation ON invariant_evaluations USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE verification_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_runs FORCE ROW LEVEL SECURITY;
CREATE POLICY verification_runs_tenant_isolation ON verification_runs USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE plan_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_drafts FORCE ROW LEVEL SECURITY;
CREATE POLICY plan_drafts_tenant_isolation ON plan_drafts USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE mission_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE mission_templates FORCE ROW LEVEL SECURITY;
CREATE POLICY mission_templates_tenant_isolation ON mission_templates USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE integration_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_proposals FORCE ROW LEVEL SECURITY;
CREATE POLICY integration_proposals_tenant_isolation ON integration_proposals USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE tenant_overhead_budget_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_overhead_budget_settings FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_overhead_budget_settings_tenant_isolation ON tenant_overhead_budget_settings USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid));

ALTER TABLE diff_gate_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE diff_gate_reports FORCE ROW LEVEL SECURITY;
CREATE POLICY diff_gate_reports_tenant_isolation ON diff_gate_reports USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE dependency_admissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE dependency_admissions FORCE ROW LEVEL SECURITY;
CREATE POLICY dependency_admissions_tenant_isolation ON dependency_admissions USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals FORCE ROW LEVEL SECURITY;
CREATE POLICY approvals_tenant_isolation ON approvals USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE standing_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE standing_approvals FORCE ROW LEVEL SECURITY;
CREATE POLICY standing_approvals_tenant_isolation ON standing_approvals USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE control_plane_overhead_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE control_plane_overhead_tasks FORCE ROW LEVEL SECURITY;
CREATE POLICY control_plane_overhead_tasks_tenant_isolation ON control_plane_overhead_tasks USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence FORCE ROW LEVEL SECURITY;
CREATE POLICY evidence_tenant_isolation ON evidence USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE attention_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE attention_items FORCE ROW LEVEL SECURITY;
CREATE POLICY attention_items_tenant_isolation ON attention_items USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE client_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY client_sessions_tenant_isolation ON client_sessions USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid));

ALTER TABLE workload_class_cost_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE workload_class_cost_metrics FORCE ROW LEVEL SECURITY;
CREATE POLICY workload_class_cost_metrics_tenant_isolation ON workload_class_cost_metrics USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE donor_artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE donor_artifacts FORCE ROW LEVEL SECURITY;
CREATE POLICY donor_artifacts_tenant_isolation ON donor_artifacts USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE feature_dna ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_dna FORCE ROW LEVEL SECURITY;
CREATE POLICY feature_dna_tenant_isolation ON feature_dna USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE captured_provider_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE captured_provider_credentials FORCE ROW LEVEL SECURITY;
CREATE POLICY captured_provider_credentials_tenant_isolation ON captured_provider_credentials USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE donor_taints ENABLE ROW LEVEL SECURITY;
ALTER TABLE donor_taints FORCE ROW LEVEL SECURITY;
CREATE POLICY donor_taints_tenant_isolation ON donor_taints USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

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

ALTER TABLE frontend_contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE frontend_contracts FORCE ROW LEVEL SECURITY;
CREATE POLICY frontend_contracts_tenant_isolation ON frontend_contracts USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE pxg_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE pxg_nodes FORCE ROW LEVEL SECURITY;
CREATE POLICY pxg_nodes_tenant_isolation ON pxg_nodes USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE pxg_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE pxg_edges FORCE ROW LEVEL SECURITY;
CREATE POLICY pxg_edges_tenant_isolation ON pxg_edges USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE frontend_coverage_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE frontend_coverage_snapshots FORCE ROW LEVEL SECURITY;
CREATE POLICY frontend_coverage_snapshots_tenant_isolation ON frontend_coverage_snapshots USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE frontend_locks ENABLE ROW LEVEL SECURITY;
ALTER TABLE frontend_locks FORCE ROW LEVEL SECURITY;
CREATE POLICY frontend_locks_tenant_isolation ON frontend_locks USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE frontend_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE frontend_candidates FORCE ROW LEVEL SECURITY;
CREATE POLICY frontend_candidates_tenant_isolation ON frontend_candidates USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE frontend_mutations ENABLE ROW LEVEL SECURITY;
ALTER TABLE frontend_mutations FORCE ROW LEVEL SECURITY;
CREATE POLICY frontend_mutations_tenant_isolation ON frontend_mutations USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE design_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE design_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY design_sessions_tenant_isolation ON design_sessions USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE design_artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE design_artifacts FORCE ROW LEVEL SECURITY;
CREATE POLICY design_artifacts_tenant_isolation ON design_artifacts USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE frontend_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE frontend_conversations FORCE ROW LEVEL SECURITY;
CREATE POLICY frontend_conversations_tenant_isolation ON frontend_conversations USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE frontend_conversation_turns ENABLE ROW LEVEL SECURITY;
ALTER TABLE frontend_conversation_turns FORCE ROW LEVEL SECURITY;
CREATE POLICY frontend_conversation_turns_tenant_isolation ON frontend_conversation_turns USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));

ALTER TABLE frontend_preview_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE frontend_preview_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY frontend_preview_sessions_tenant_isolation ON frontend_preview_sessions USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)) WITH CHECK (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) AND project_id = CAST(current_setting('dde.project_id', true) AS uuid));
