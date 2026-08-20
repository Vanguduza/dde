"""Chapter 3.10's immutable-definition-hash principle, applied to
`CapabilityLease`. Chapter 3.10 names `CapabilityLease` among the objects
whose "definition" is immutable and content-hashed, but -- like
`CapabilityDescriptor` (see `engine.capabilities.hashing`'s module
docstring) -- its own named-hash-field list (`plan_hash`, `decision_hash`,
`assembly_hash`, `graph_hash`, `oracle_version`) never actually names one
for a lease. `lease_hash` exists for the same reason `descriptor_hash`
does: idempotent re-requesting of the identical lease definition
(`engine.capabilities.lease_service.CapabilityLeaseService.request`) needs
something to compare against. Computed over every field Chapter 3.8 calls
"scope" (immutable) -- excludes `status`/`denied_reason`/`revoked_at`/
`revocation_reason`/`created_at`/`updated_at`, which is exactly what that
same ownership-matrix row calls mutable.
"""

from __future__ import annotations

from uuid import UUID

from engine.core.hashing import canonical_json, sha256_hex


def lease_hash(
    *,
    tenant_id: UUID,
    project_id: UUID,
    mission_id: UUID,
    task_id: UUID,
    execution_plan_id: UUID,
    worker_run_id: UUID | None,
    environment_id: UUID | None,
    capability_id: str,
    capability_version: str,
    resource_scope: dict[str, object],
    operation_scope: str,
    constraints: dict[str, object],
) -> str:
    payload = {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "mission_id": str(mission_id),
        "task_id": str(task_id),
        "execution_plan_id": str(execution_plan_id),
        "worker_run_id": str(worker_run_id) if worker_run_id else None,
        "environment_id": str(environment_id) if environment_id else None,
        "capability_id": capability_id,
        "capability_version": capability_version,
        "resource_scope": resource_scope,
        "operation_scope": operation_scope,
        "constraints": constraints,
    }
    return sha256_hex(canonical_json(payload))
