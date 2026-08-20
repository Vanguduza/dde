"""Chapter 3.10 immutable-definition hashing for RouteDecision.

`decision_hash` covers every definition field and excludes the lifecycle/
identity columns (`decision_id`, `created_at`, `updated_at`) exactly as
`engine.context.hashing.assembly_hash` does for ContextPackage: routing the
same task against an unchanged policy and candidate universe must produce
an identical hash even though `decision_id` is always fresh.
"""

from __future__ import annotations

from uuid import UUID

from engine.core.hashing import canonical_json, sha256_hex


def decision_hash(
    *,
    tenant_id: UUID,
    project_id: UUID,
    mission_id: UUID,
    task_id: UUID,
    candidates: list[dict[str, object]],
    selected_worker_profile_id: str,
    workload_class: str,
    required_capabilities: list[str],
    required_environment_class: str,
    reason_codes: list[str],
    selection_source: str,
    selection_propensity: float,
    fallback_plan: list[dict[str, object]],
    escalation_plan: list[dict[str, object]],
    policy_version: str,
) -> str:
    payload = {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "mission_id": str(mission_id),
        "task_id": str(task_id),
        "candidates": candidates,
        "selected_worker_profile_id": selected_worker_profile_id,
        "workload_class": workload_class,
        "required_capabilities": required_capabilities,
        "required_environment_class": required_environment_class,
        "reason_codes": reason_codes,
        "selection_source": selection_source,
        "selection_propensity": selection_propensity,
        "fallback_plan": fallback_plan,
        "escalation_plan": escalation_plan,
        "policy_version": policy_version,
    }
    return sha256_hex(canonical_json(payload))
