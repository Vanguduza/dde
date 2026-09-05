# ruff: noqa: E501
"""AI Conversation Fabric shared authorities.

Provider/session federation, policies, memory/context, skills, teams, research,
automations/hooks, claim annotations and Hermes experience-intelligence inputs.
Discovery is separate from certification and no table grants execution authority.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None

_SCOPE_POLICY = (
    "tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) "
    "AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)"
)


def _rls(table: str) -> None:
    op.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        text(
            f"CREATE POLICY {table}_tenant_isolation ON {table} USING ({_SCOPE_POLICY}) WITH CHECK ({_SCOPE_POLICY})"
        )
    )


def upgrade() -> None:
    op.execute(
        text(
            "CREATE TABLE ai_conversation_policies (\n    policy_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    name text NOT NULL,\n    reasoning_effort text NOT NULL,\n    permission_profile text NOT NULL,\n    toolset_ids jsonb NOT NULL DEFAULT '[]'::jsonb,\n    allowed_capability_ids jsonb NOT NULL DEFAULT '[]'::jsonb,\n    denied_capability_ids jsonb NOT NULL DEFAULT '[]'::jsonb,\n    fallback_chain jsonb NOT NULL DEFAULT '[]'::jsonb,\n    max_turns integer,\n    context_token_budget integer NOT NULL,\n    cost_budget_usd numeric,\n    quality_priority integer NOT NULL,\n    latency_priority integer NOT NULL,\n    independent_review_required boolean NOT NULL,\n    created_by uuid,\n    lock_version integer NOT NULL DEFAULT 1,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (policy_id),\n    UNIQUE (project_id, name),\n    CHECK (context_token_budget > 0),\n    CHECK (quality_priority BETWEEN 0 AND 100 AND latency_priority BETWEEN 0 AND 100)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE agent_interop_endpoints (\n    endpoint_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    harness_id text NOT NULL,\n    protocol text NOT NULL,\n    executable_or_uri text NOT NULL,\n    installation_version text,\n    discovery_state text NOT NULL,\n    certification_state text NOT NULL,\n    discovered_capabilities jsonb NOT NULL DEFAULT '{}'::jsonb,\n    certified_capabilities jsonb NOT NULL DEFAULT '{}'::jsonb,\n    certification_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    health_state text NOT NULL,\n    config_hash text,\n    last_probe_at timestamptz,\n    last_error text,\n    lock_version integer NOT NULL DEFAULT 1,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (endpoint_id),\n    UNIQUE (project_id, harness_id, protocol, executable_or_uri)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE worker_sessions (\n    worker_session_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    mission_id uuid,\n    task_id uuid,\n    endpoint_id uuid NOT NULL,\n    worker_profile_id text,\n    provider_session_ref text,\n    requested_model_id text,\n    serving_model_id text,\n    workspace_id uuid,\n    state text NOT NULL,\n    capability_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,\n    context_package_hash text,\n    tool_policy_hash text,\n    session_config_hash text NOT NULL,\n    parent_session_id uuid,\n    forked_from_session_id uuid,\n    last_error text,\n    lock_version integer NOT NULL DEFAULT 1,\n    created_at timestamptz NOT NULL,\n    last_activity_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (worker_session_id)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE provider_capacity_snapshots (\n    snapshot_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    endpoint_id uuid NOT NULL,\n    provider_id text NOT NULL,\n    state text NOT NULL,\n    reset_at timestamptz,\n    reset_source text,\n    confidence numeric NOT NULL,\n    active_concurrency integer,\n    max_concurrency integer,\n    latency_ms integer,\n    recent_failures integer NOT NULL,\n    input_cost_per_million numeric,\n    output_cost_per_million numeric,\n    quota_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,\n    observed_at timestamptz NOT NULL,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (snapshot_id)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE ai_provider_invocations (\n    invocation_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    conversation_id uuid NOT NULL,\n    turn_id uuid,\n    worker_session_id uuid,\n    endpoint_id uuid NOT NULL,\n    fallback_parent_id uuid,\n    requested_profile_id text,\n    requested_model_id text,\n    serving_model_id text,\n    reasoning_effort text NOT NULL,\n    state text NOT NULL,\n    prompt_hash text NOT NULL,\n    context_hash text NOT NULL,\n    policy_hash text NOT NULL,\n    approval_id uuid,\n    worker_run_id uuid,\n    input_tokens integer,\n    output_tokens integer,\n    cache_tokens integer,\n    reasoning_tokens integer,\n    cost_usd numeric,\n    latency_ms integer,\n    result_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    error_code text,\n    error_detail text,\n    created_at timestamptz NOT NULL,\n    started_at timestamptz,\n    completed_at timestamptz,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (invocation_id)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE ai_memory_items (\n    memory_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    scope_kind text NOT NULL,\n    scope_ref text NOT NULL,\n    trust_class text NOT NULL,\n    status text NOT NULL,\n    content text NOT NULL,\n    content_hash text NOT NULL,\n    content_size_bytes integer NOT NULL,\n    token_estimate integer NOT NULL,\n    storage_backend text NOT NULL,\n    storage_key text,\n    source_type text NOT NULL,\n    source_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    proposed_by_profile_id text,\n    approved_by uuid,\n    approved_at timestamptz,\n    supersedes_memory_id uuid,\n    fresh_until timestamptz,\n    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,\n    lock_version integer NOT NULL DEFAULT 1,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (memory_id)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE ai_context_snapshots (\n    context_snapshot_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    conversation_id uuid NOT NULL,\n    turn_id uuid,\n    predecessor_snapshot_id uuid,\n    reason text NOT NULL,\n    summary text,\n    retained_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    omitted_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    omission_reasons jsonb NOT NULL DEFAULT '{}'::jsonb,\n    item_manifest jsonb NOT NULL DEFAULT '[]'::jsonb,\n    estimated_tokens integer NOT NULL,\n    budget_tokens integer NOT NULL,\n    context_hash text NOT NULL,\n    archive_storage_backend text,\n    archive_storage_key text,\n    archive_hash text,\n    archive_size_bytes integer,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (context_snapshot_id)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE ai_skills (\n    skill_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    slug text NOT NULL,\n    version text NOT NULL,\n    title text NOT NULL,\n    description text NOT NULL,\n    instructions text NOT NULL,\n    source_kind text NOT NULL,\n    source_ref text,\n    provenance_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    license text,\n    manifest_hash text NOT NULL,\n    required_capability_ids jsonb NOT NULL DEFAULT '[]'::jsonb,\n    toolset_ids jsonb NOT NULL DEFAULT '[]'::jsonb,\n    status text NOT NULL,\n    evaluation_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    certified_by uuid,\n    certified_at timestamptz,\n    parent_skill_id uuid,\n    lock_version integer NOT NULL DEFAULT 1,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (skill_id),\n    UNIQUE (project_id, slug, version)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE ai_agent_teams (\n    team_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    conversation_id uuid NOT NULL,\n    mission_id uuid,\n    strategy text NOT NULL,\n    state text NOT NULL,\n    manager_profile_id text,\n    max_depth integer NOT NULL,\n    max_children integer NOT NULL,\n    aggregate_budget jsonb NOT NULL DEFAULT '{}'::jsonb,\n    members jsonb NOT NULL DEFAULT '[]'::jsonb,\n    result_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    lock_version integer NOT NULL DEFAULT 1,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (team_id)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE ai_research_artifacts (\n    research_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    conversation_id uuid NOT NULL,\n    mission_id uuid,\n    created_from_turn_id uuid,\n    mode text NOT NULL,\n    question text NOT NULL,\n    scope jsonb NOT NULL DEFAULT '{}'::jsonb,\n    state text NOT NULL,\n    source_ledger jsonb NOT NULL DEFAULT '[]'::jsonb,\n    findings jsonb NOT NULL DEFAULT '[]'::jsonb,\n    hypotheses jsonb NOT NULL DEFAULT '[]'::jsonb,\n    unresolved_questions jsonb NOT NULL DEFAULT '[]'::jsonb,\n    confidence numeric,\n    result_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    lock_version integer NOT NULL DEFAULT 1,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (research_id)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE ai_automations (\n    automation_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    conversation_id uuid NOT NULL,\n    mission_id uuid,\n    name text NOT NULL,\n    schedule_kind text NOT NULL,\n    schedule_expression text NOT NULL,\n    timezone text NOT NULL,\n    action_kind text NOT NULL,\n    action_payload jsonb NOT NULL DEFAULT '{}'::jsonb,\n    state text NOT NULL,\n    next_run_at timestamptz,\n    last_run_at timestamptz,\n    last_result_ref text,\n    run_count integer NOT NULL,\n    created_by uuid,\n    lock_version integer NOT NULL DEFAULT 1,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (automation_id)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE ai_hooks (\n    hook_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    conversation_id uuid,\n    name text NOT NULL,\n    event_kind text NOT NULL,\n    action_kind text NOT NULL,\n    condition jsonb NOT NULL DEFAULT '{}'::jsonb,\n    action_payload jsonb NOT NULL DEFAULT '{}'::jsonb,\n    state text NOT NULL,\n    last_triggered_at timestamptz,\n    trigger_count integer NOT NULL,\n    created_by uuid,\n    lock_version integer NOT NULL DEFAULT 1,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (hook_id)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE ai_claims (\n    claim_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    conversation_id uuid NOT NULL,\n    turn_id uuid NOT NULL,\n    claim_text text NOT NULL,\n    epistemic_class text NOT NULL,\n    confidence numeric,\n    source_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    verification_state text NOT NULL,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (claim_id)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE experience_records (\n    experience_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    mission_id uuid,\n    task_id uuid,\n    worker_run_id uuid,\n    worker_session_id uuid,\n    task_signature jsonb NOT NULL DEFAULT '{}'::jsonb,\n    worker_configuration jsonb NOT NULL DEFAULT '{}'::jsonb,\n    outcome jsonb NOT NULL DEFAULT '{}'::jsonb,\n    economics jsonb NOT NULL DEFAULT '{}'::jsonb,\n    failure_signatures jsonb NOT NULL DEFAULT '[]'::jsonb,\n    verification_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    authority_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (experience_id)\n);"
        )
    )
    op.execute(
        text(
            "CREATE TABLE routing_insight_candidates (\n    insight_id uuid NOT NULL,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    source_kind text NOT NULL,\n    source_ref text NOT NULL,\n    proposal jsonb NOT NULL DEFAULT '{}'::jsonb,\n    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    confidence numeric NOT NULL,\n    state text NOT NULL,\n    evaluation_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    promoted_policy_ref text,\n    promoted_by uuid,\n    promoted_at timestamptz,\n    lock_version integer NOT NULL DEFAULT 1,\n    created_at timestamptz NOT NULL,\n    updated_at timestamptz NOT NULL,\n    PRIMARY KEY (insight_id)\n);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_conversation_policies ADD CONSTRAINT ai_conversation_policies_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_conversation_policies ADD CONSTRAINT ai_conversation_policies_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_conversation_policies ADD CONSTRAINT ai_conversation_policies_created_by_fkey FOREIGN KEY (created_by) REFERENCES principals (principal_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE agent_interop_endpoints ADD CONSTRAINT agent_interop_endpoints_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE agent_interop_endpoints ADD CONSTRAINT agent_interop_endpoints_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE worker_sessions ADD CONSTRAINT worker_sessions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE worker_sessions ADD CONSTRAINT worker_sessions_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE worker_sessions ADD CONSTRAINT worker_sessions_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE worker_sessions ADD CONSTRAINT worker_sessions_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE worker_sessions ADD CONSTRAINT worker_sessions_endpoint_id_fkey FOREIGN KEY (endpoint_id) REFERENCES agent_interop_endpoints (endpoint_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE worker_sessions ADD CONSTRAINT worker_sessions_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES workspaces (workspace_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE worker_sessions ADD CONSTRAINT worker_sessions_parent_session_id_fkey FOREIGN KEY (parent_session_id) REFERENCES worker_sessions (worker_session_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE worker_sessions ADD CONSTRAINT worker_sessions_forked_from_session_id_fkey FOREIGN KEY (forked_from_session_id) REFERENCES worker_sessions (worker_session_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE provider_capacity_snapshots ADD CONSTRAINT provider_capacity_snapshots_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE provider_capacity_snapshots ADD CONSTRAINT provider_capacity_snapshots_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE provider_capacity_snapshots ADD CONSTRAINT provider_capacity_snapshots_endpoint_id_fkey FOREIGN KEY (endpoint_id) REFERENCES agent_interop_endpoints (endpoint_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_provider_invocations ADD CONSTRAINT ai_provider_invocations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_provider_invocations ADD CONSTRAINT ai_provider_invocations_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_provider_invocations ADD CONSTRAINT ai_provider_invocations_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES frontend_conversations (conversation_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_provider_invocations ADD CONSTRAINT ai_provider_invocations_turn_id_fkey FOREIGN KEY (turn_id) REFERENCES frontend_conversation_turns (turn_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_provider_invocations ADD CONSTRAINT ai_provider_invocations_worker_session_id_fkey FOREIGN KEY (worker_session_id) REFERENCES worker_sessions (worker_session_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_provider_invocations ADD CONSTRAINT ai_provider_invocations_endpoint_id_fkey FOREIGN KEY (endpoint_id) REFERENCES agent_interop_endpoints (endpoint_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_provider_invocations ADD CONSTRAINT ai_provider_invocations_fallback_parent_id_fkey FOREIGN KEY (fallback_parent_id) REFERENCES ai_provider_invocations (invocation_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_provider_invocations ADD CONSTRAINT ai_provider_invocations_approval_id_fkey FOREIGN KEY (approval_id) REFERENCES approvals (approval_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_provider_invocations ADD CONSTRAINT ai_provider_invocations_worker_run_id_fkey FOREIGN KEY (worker_run_id) REFERENCES worker_runs (run_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_memory_items ADD CONSTRAINT ai_memory_items_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_memory_items ADD CONSTRAINT ai_memory_items_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_memory_items ADD CONSTRAINT ai_memory_items_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES principals (principal_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_memory_items ADD CONSTRAINT ai_memory_items_supersedes_memory_id_fkey FOREIGN KEY (supersedes_memory_id) REFERENCES ai_memory_items (memory_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_context_snapshots ADD CONSTRAINT ai_context_snapshots_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_context_snapshots ADD CONSTRAINT ai_context_snapshots_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_context_snapshots ADD CONSTRAINT ai_context_snapshots_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES frontend_conversations (conversation_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_context_snapshots ADD CONSTRAINT ai_context_snapshots_turn_id_fkey FOREIGN KEY (turn_id) REFERENCES frontend_conversation_turns (turn_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_context_snapshots ADD CONSTRAINT ai_context_snapshots_predecessor_snapshot_id_fkey FOREIGN KEY (predecessor_snapshot_id) REFERENCES ai_context_snapshots (context_snapshot_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_skills ADD CONSTRAINT ai_skills_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_skills ADD CONSTRAINT ai_skills_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_skills ADD CONSTRAINT ai_skills_certified_by_fkey FOREIGN KEY (certified_by) REFERENCES principals (principal_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_skills ADD CONSTRAINT ai_skills_parent_skill_id_fkey FOREIGN KEY (parent_skill_id) REFERENCES ai_skills (skill_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_agent_teams ADD CONSTRAINT ai_agent_teams_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_agent_teams ADD CONSTRAINT ai_agent_teams_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_agent_teams ADD CONSTRAINT ai_agent_teams_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES frontend_conversations (conversation_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_agent_teams ADD CONSTRAINT ai_agent_teams_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_research_artifacts ADD CONSTRAINT ai_research_artifacts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_research_artifacts ADD CONSTRAINT ai_research_artifacts_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_research_artifacts ADD CONSTRAINT ai_research_artifacts_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES frontend_conversations (conversation_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_research_artifacts ADD CONSTRAINT ai_research_artifacts_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_research_artifacts ADD CONSTRAINT ai_research_artifacts_created_from_turn_id_fkey FOREIGN KEY (created_from_turn_id) REFERENCES frontend_conversation_turns (turn_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_automations ADD CONSTRAINT ai_automations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_automations ADD CONSTRAINT ai_automations_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_automations ADD CONSTRAINT ai_automations_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES frontend_conversations (conversation_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_automations ADD CONSTRAINT ai_automations_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_automations ADD CONSTRAINT ai_automations_created_by_fkey FOREIGN KEY (created_by) REFERENCES principals (principal_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_hooks ADD CONSTRAINT ai_hooks_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_hooks ADD CONSTRAINT ai_hooks_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_hooks ADD CONSTRAINT ai_hooks_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES frontend_conversations (conversation_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_hooks ADD CONSTRAINT ai_hooks_created_by_fkey FOREIGN KEY (created_by) REFERENCES principals (principal_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_claims ADD CONSTRAINT ai_claims_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_claims ADD CONSTRAINT ai_claims_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_claims ADD CONSTRAINT ai_claims_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES frontend_conversations (conversation_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE ai_claims ADD CONSTRAINT ai_claims_turn_id_fkey FOREIGN KEY (turn_id) REFERENCES frontend_conversation_turns (turn_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE experience_records ADD CONSTRAINT experience_records_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE experience_records ADD CONSTRAINT experience_records_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE experience_records ADD CONSTRAINT experience_records_mission_id_fkey FOREIGN KEY (mission_id) REFERENCES missions (mission_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE experience_records ADD CONSTRAINT experience_records_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks (task_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE experience_records ADD CONSTRAINT experience_records_worker_run_id_fkey FOREIGN KEY (worker_run_id) REFERENCES worker_runs (run_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE experience_records ADD CONSTRAINT experience_records_worker_session_id_fkey FOREIGN KEY (worker_session_id) REFERENCES worker_sessions (worker_session_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE routing_insight_candidates ADD CONSTRAINT routing_insight_candidates_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE routing_insight_candidates ADD CONSTRAINT routing_insight_candidates_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (project_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE routing_insight_candidates ADD CONSTRAINT routing_insight_candidates_promoted_by_fkey FOREIGN KEY (promoted_by) REFERENCES principals (principal_id);"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_chat_checkpoints ADD COLUMN conversation_context jsonb"
        )
    )
    op.execute(text("ALTER TABLE frontend_conversations ADD COLUMN policy_id uuid"))
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD COLUMN active_worker_session_id uuid"
        )
    )
    op.execute(
        text("ALTER TABLE frontend_conversations ADD COLUMN context_domain text")
    )
    op.execute(
        text("ALTER TABLE frontend_conversations ADD COLUMN active_task_id uuid")
    )
    op.execute(
        text("ALTER TABLE frontend_conversations ADD COLUMN active_worker_run_id uuid")
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD COLUMN active_verification_run_id uuid"
        )
    )
    op.execute(
        text("ALTER TABLE frontend_conversations ADD COLUMN active_artifact_ref text")
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD CONSTRAINT frontend_conversations_context_domain_known CHECK (context_domain IS NULL OR context_domain IN ('DDE','MISSION','TASK','FRONTEND_STUDIO','QUALITY','RESEARCH','DECISIONS','FLEET','EVIDENCE'))"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD CONSTRAINT frontend_conversations_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES ai_conversation_policies(policy_id)"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD CONSTRAINT frontend_conversations_active_worker_session_id_fkey FOREIGN KEY (active_worker_session_id) REFERENCES worker_sessions(worker_session_id)"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD CONSTRAINT frontend_conversations_active_task_id_fkey FOREIGN KEY (active_task_id) REFERENCES tasks(task_id)"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD CONSTRAINT frontend_conversations_active_worker_run_id_fkey FOREIGN KEY (active_worker_run_id) REFERENCES worker_runs(run_id)"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD CONSTRAINT frontend_conversations_active_verification_run_id_fkey FOREIGN KEY (active_verification_run_id) REFERENCES verification_runs(verification_run_id)"
        )
    )
    _rls("ai_conversation_policies")
    _rls("agent_interop_endpoints")
    _rls("worker_sessions")
    _rls("provider_capacity_snapshots")
    _rls("ai_provider_invocations")
    _rls("ai_memory_items")
    _rls("ai_context_snapshots")
    _rls("ai_skills")
    _rls("ai_agent_teams")
    _rls("ai_research_artifacts")
    _rls("ai_automations")
    _rls("ai_hooks")
    _rls("ai_claims")
    _rls("experience_records")
    _rls("routing_insight_candidates")
    op.execute(
        text(
            "CREATE INDEX ai_provider_invocations_conversation_idx ON ai_provider_invocations (conversation_id, created_at DESC)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX ai_memory_scope_idx ON ai_memory_items (scope_kind, scope_ref, status, updated_at DESC)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX ai_context_snapshots_conversation_idx ON ai_context_snapshots (conversation_id, created_at DESC)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX ai_skills_status_idx ON ai_skills (project_id, status, slug)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX ai_agent_teams_conversation_idx ON ai_agent_teams (conversation_id, updated_at DESC)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX ai_research_artifacts_conversation_idx ON ai_research_artifacts (conversation_id, updated_at DESC)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX ai_automations_due_idx ON ai_automations (state, next_run_at)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX ai_hooks_event_idx ON ai_hooks (project_id, event_kind, state)"
        )
    )
    op.execute(
        text("CREATE INDEX ai_claims_turn_idx ON ai_claims (turn_id, created_at)")
    )
    op.execute(
        text(
            "CREATE INDEX provider_capacity_endpoint_idx ON provider_capacity_snapshots (endpoint_id, observed_at DESC)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX worker_sessions_activity_idx ON worker_sessions (project_id, state, last_activity_at DESC)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX experience_records_task_idx ON experience_records (project_id, task_id, created_at DESC)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX routing_insight_state_idx ON routing_insight_candidates (project_id, state, updated_at DESC)"
        )
    )


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS routing_insight_state_idx"))
    op.execute(text("DROP INDEX IF EXISTS experience_records_task_idx"))
    op.execute(text("DROP INDEX IF EXISTS worker_sessions_activity_idx"))
    op.execute(text("DROP INDEX IF EXISTS provider_capacity_endpoint_idx"))
    op.execute(text("DROP INDEX IF EXISTS ai_claims_turn_idx"))
    op.execute(text("DROP INDEX IF EXISTS ai_hooks_event_idx"))
    op.execute(text("DROP INDEX IF EXISTS ai_automations_due_idx"))
    op.execute(text("DROP INDEX IF EXISTS ai_research_artifacts_conversation_idx"))
    op.execute(text("DROP INDEX IF EXISTS ai_agent_teams_conversation_idx"))
    op.execute(text("DROP INDEX IF EXISTS ai_skills_status_idx"))
    op.execute(text("DROP INDEX IF EXISTS ai_context_snapshots_conversation_idx"))
    op.execute(text("DROP INDEX IF EXISTS ai_memory_scope_idx"))
    op.execute(text("DROP INDEX IF EXISTS ai_provider_invocations_conversation_idx"))
    op.execute(
        text(
            "ALTER TABLE frontend_chat_checkpoints DROP COLUMN IF EXISTS conversation_context"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations DROP CONSTRAINT IF EXISTS frontend_conversations_active_verification_run_id_fkey"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations DROP CONSTRAINT IF EXISTS frontend_conversations_active_worker_run_id_fkey"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations DROP CONSTRAINT IF EXISTS frontend_conversations_active_task_id_fkey"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations DROP CONSTRAINT IF EXISTS frontend_conversations_context_domain_known"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations DROP CONSTRAINT IF EXISTS frontend_conversations_active_worker_session_id_fkey"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations DROP CONSTRAINT IF EXISTS frontend_conversations_policy_id_fkey"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations DROP COLUMN IF EXISTS active_artifact_ref"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations DROP COLUMN IF EXISTS active_verification_run_id"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations DROP COLUMN IF EXISTS active_worker_run_id"
        )
    )
    op.execute(
        text("ALTER TABLE frontend_conversations DROP COLUMN IF EXISTS active_task_id")
    )
    op.execute(
        text("ALTER TABLE frontend_conversations DROP COLUMN IF EXISTS context_domain")
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations DROP COLUMN IF EXISTS active_worker_session_id"
        )
    )
    op.execute(
        text("ALTER TABLE frontend_conversations DROP COLUMN IF EXISTS policy_id")
    )
    op.execute(text("DROP TABLE IF EXISTS routing_insight_candidates"))
    op.execute(text("DROP TABLE IF EXISTS experience_records"))
    op.execute(text("DROP TABLE IF EXISTS ai_claims"))
    op.execute(text("DROP TABLE IF EXISTS ai_hooks"))
    op.execute(text("DROP TABLE IF EXISTS ai_automations"))
    op.execute(text("DROP TABLE IF EXISTS ai_research_artifacts"))
    op.execute(text("DROP TABLE IF EXISTS ai_agent_teams"))
    op.execute(text("DROP TABLE IF EXISTS ai_skills"))
    op.execute(text("DROP TABLE IF EXISTS ai_context_snapshots"))
    op.execute(text("DROP TABLE IF EXISTS ai_memory_items"))
    op.execute(text("DROP TABLE IF EXISTS ai_provider_invocations"))
    op.execute(text("DROP TABLE IF EXISTS provider_capacity_snapshots"))
    op.execute(text("DROP TABLE IF EXISTS worker_sessions"))
    op.execute(text("DROP TABLE IF EXISTS agent_interop_endpoints"))
    op.execute(text("DROP TABLE IF EXISTS ai_conversation_policies"))
