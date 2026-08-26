# Generated object catalog

Generated from `schemas/objects`. Do not edit.

## Organization

- table: `organizations`
- primary key: organization_id
- tenant scoped: false
- project scoped: false
- lock_version: false

## Tenant

- table: `tenants`
- primary key: tenant_id
- tenant scoped: true
- project scoped: false
- lock_version: false

## Project

- table: `projects`
- primary key: project_id
- tenant scoped: true
- project scoped: false
- lock_version: false

## Principal

- table: `principals`
- primary key: principal_id
- tenant scoped: true
- project scoped: false
- lock_version: false

## PrincipalGrant

- table: `principal_grants`
- primary key: grant_id
- tenant scoped: true
- project scoped: false
- lock_version: false

## CapabilityDescriptor

- table: `capabilities`
- primary key: descriptor_id
- tenant scoped: false
- project scoped: false
- lock_version: false

## ProductConstitutionVersion

- table: `product_constitution_versions`
- primary key: version_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## Requirement

- table: `requirements`
- primary key: requirement_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## Edr

- table: `edrs`
- primary key: edr_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## Mission

- table: `missions`
- primary key: mission_id
- tenant scoped: true
- project scoped: true
- lock_version: true

## TaskGraph

- table: `task_graphs`
- primary key: graph_id
- tenant scoped: true
- project scoped: true
- lock_version: true

## Task

- table: `tasks`
- primary key: task_id
- tenant scoped: true
- project scoped: true
- lock_version: true

## TaskGraphEdge

- table: `task_graph_edges`
- primary key: edge_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## ContextPackage

- table: `context_packages`
- primary key: package_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## ContextIndex

- table: `context_indexes`
- primary key: index_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## ContextChunk

- table: `context_chunks`
- primary key: chunk_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## EvalCase

- table: `eval_cases`
- primary key: eval_case_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## PromotionGateRun

- table: `promotion_gate_runs`
- primary key: run_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## ContextConflict

- table: `context_conflicts`
- primary key: conflict_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## ContextCriticFinding

- table: `context_critic_findings`
- primary key: finding_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## AssertedEdge

- table: `asserted_edges`
- primary key: edge_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## DerivedEdge

- table: `derived_edges`
- primary key: derived_edge_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## FailureAttribution

- table: `failure_attributions`
- primary key: attribution_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## RouteDecision

- table: `route_decisions`
- primary key: decision_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## RoutingDecisionOutcome

- table: `routing_decision_outcomes`
- primary key: outcome_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## RoutingSimulationRun

- table: `routing_simulation_runs`
- primary key: run_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## ExperienceRecord

- table: `experience_records`
- primary key: experience_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## ExecutionEnvironment

- table: `execution_environments`
- primary key: environment_id
- tenant scoped: true
- project scoped: true
- lock_version: true

## Workspace

- table: `workspaces`
- primary key: workspace_id
- tenant scoped: true
- project scoped: true
- lock_version: true

## WriteScopeLease

- table: `write_scope_leases`
- primary key: lease_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## ExecutionPlan

- table: `execution_plans`
- primary key: plan_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## TaskAttempt

- table: `task_attempts`
- primary key: attempt_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## WorkerRun

- table: `worker_runs`
- primary key: run_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## WorkerEvent

- table: `worker_events`
- primary key: event_id, occurred_at
- tenant scoped: true
- project scoped: true
- lock_version: false

## CapabilityLease

- table: `capability_leases`
- primary key: lease_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## CredentialHandle

- table: `credential_handles`
- primary key: handle_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## ExternalEffect

- table: `external_effects`
- primary key: effect_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## Checkpoint

- table: `checkpoints`
- primary key: checkpoint_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## Artifact

- table: `artifacts`
- primary key: artifact_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## SeedDataset

- table: `seed_datasets`
- primary key: dataset_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## AcceptanceOracle

- table: `acceptance_oracles`
- primary key: oracle_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## MissionOracleEvaluation

- table: `mission_oracle_evaluations`
- primary key: evaluation_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## ProductEnvironment

- table: `product_environments`
- primary key: product_env_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## DomainInvariant

- table: `domain_invariants`
- primary key: invariant_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## InvariantEvaluation

- table: `invariant_evaluations`
- primary key: evaluation_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## VerificationRun

- table: `verification_runs`
- primary key: verification_run_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## PlanDraft

- table: `plan_drafts`
- primary key: draft_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## MissionTemplate

- table: `mission_templates`
- primary key: template_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## IntegrationProposal

- table: `integration_proposals`
- primary key: proposal_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## TenantOverheadBudgetSettings

- table: `tenant_overhead_budget_settings`
- primary key: tenant_id
- tenant scoped: true
- project scoped: false
- lock_version: false

## DiffGateReport

- table: `diff_gate_reports`
- primary key: report_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## DependencyAdmission

- table: `dependency_admissions`
- primary key: admission_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## Approval

- table: `approvals`
- primary key: approval_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## StandingApproval

- table: `standing_approvals`
- primary key: standing_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## ControlPlaneOverheadTask

- table: `control_plane_overhead_tasks`
- primary key: overhead_task_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## Evidence

- table: `evidence`
- primary key: evidence_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## AttentionItem

- table: `attention_items`
- primary key: attention_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## ClientSession

- table: `client_sessions`
- primary key: session_id
- tenant scoped: true
- project scoped: false
- lock_version: false

## WorkloadClassCostMetrics

- table: `workload_class_cost_metrics`
- primary key: metric_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## DonorArtifact

- table: `donor_artifacts`
- primary key: donor_artifact_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## FeatureDNA

- table: `feature_dna`
- primary key: feature_dna_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## CapturedProviderCredential

- table: `captured_provider_credentials`
- primary key: capture_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## DonorTaint

- table: `donor_taints`
- primary key: donor_taint_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## Event

- table: `events`
- primary key: event_id, occurred_at
- tenant scoped: true
- project scoped: true
- lock_version: false

## Outbox

- table: `outbox`
- primary key: outbox_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## CommandIdempotency

- table: `command_idempotency`
- primary key: command_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## AuditEvent

- table: `audit_events`
- primary key: audit_event_id
- tenant scoped: true
- project scoped: false
- lock_version: false
