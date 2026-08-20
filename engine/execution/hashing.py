"""Chapter 3.10 immutable-definition hashing for ExecutionPlan.

`plan_hash` covers every definition field and excludes the lifecycle/
identity columns (`plan_id`, `status`, `approved_at`, `started_at`,
`ended_at`, `created_at`, `updated_at`) exactly as `engine.routing.hashing.
decision_hash` does for RouteDecision: re-planning the same task against an
unchanged RouteDecision/ContextPackage/policy must produce an identical hash
even though `plan_id` is always fresh.
"""

from __future__ import annotations

from uuid import UUID

from engine.core.hashing import canonical_json, sha256_hex


def plan_hash(
    *,
    tenant_id: UUID,
    project_id: UUID,
    mission_id: UUID,
    task_id: UUID,
    route_decision_id: UUID,
    context_package_id: UUID,
    worker_profile_id: str,
    execution_environment_id: UUID,
    workspace_policy: dict[str, object],
    capability_requirements: list[str],
    enforcement_tier: str,
    autonomy_level: int,
    resource_budget: dict[str, object],
    time_budget: dict[str, object],
    token_budget: dict[str, object],
    network_policy: dict[str, object],
    filesystem_policy: dict[str, object],
    checkpoint_policy: dict[str, object],
    retry_policy: dict[str, object],
    escalation_policy: dict[str, object],
) -> str:
    payload = {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "mission_id": str(mission_id),
        "task_id": str(task_id),
        "route_decision_id": str(route_decision_id),
        "context_package_id": str(context_package_id),
        "worker_profile_id": worker_profile_id,
        "execution_environment_id": str(execution_environment_id),
        "workspace_policy": workspace_policy,
        "capability_requirements": capability_requirements,
        "enforcement_tier": enforcement_tier,
        "autonomy_level": autonomy_level,
        "resource_budget": resource_budget,
        "time_budget": time_budget,
        "token_budget": token_budget,
        "network_policy": network_policy,
        "filesystem_policy": filesystem_policy,
        "checkpoint_policy": checkpoint_policy,
        "retry_policy": retry_policy,
        "escalation_policy": escalation_policy,
    }
    return sha256_hex(canonical_json(payload))
