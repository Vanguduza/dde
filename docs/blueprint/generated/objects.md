# Generated object catalog

Generated from `schemas/objects`. Do not edit.

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

## RouteDecision

- table: `route_decisions`
- primary key: decision_id
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

## Artifact

- table: `artifacts`
- primary key: artifact_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## AcceptanceOracle

- table: `acceptance_oracles`
- primary key: oracle_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## VerificationRun

- table: `verification_runs`
- primary key: verification_run_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## IntegrationProposal

- table: `integration_proposals`
- primary key: proposal_id
- tenant scoped: true
- project scoped: true
- lock_version: false

## Evidence

- table: `evidence`
- primary key: evidence_id
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
- project scoped: true
- lock_version: false
