"""Chapter 3.10's general immutable-definition-hash principle, applied to
`CapabilityDescriptor`. The chapter's own explicit hash-field list (`plan_
hash`, `decision_hash`, `assembly_hash`, `graph_hash`, `oracle_version`)
does not name a capability descriptor hash -- Chapter 3.10 never actually
lists `CapabilityDescriptor` among its immutable definitions at all -- but
9.1's own field list gives every descriptor a `version` and 9.5 states
"re-admission is required on any descriptor or version change", which only
makes sense if a definition's content is checkable. `descriptor_hash`
mirrors `engine.verification.hashing.oracle_version_hash`'s convention:
computed over definition fields only, excluding identity
(`descriptor_id`), lifecycle (`certification_status`, `lifecycle_status`,
`supersedes_descriptor_id`, `superseded_by_descriptor_id`, `deprecated_at`,
`retired_at`) and provenance-of-registration (`registered_by`,
`created_at`, `updated_at`) columns, so re-registering the same
`capability_id`+`version` with the same definition is idempotent
(`engine.capabilities.service.CapabilityRegistryService.register`) even
though every other column on the row is fresh.
"""

from __future__ import annotations

from uuid import UUID

from engine.core.hashing import canonical_json, sha256_hex


def descriptor_hash(
    *,
    capability_id: str,
    version: str,
    category: str,
    summary: str,
    interface_schema_ref: str | None,
    input_schema_ref: str | None,
    output_schema_ref: str | None,
    implementations: list[str],
    supported_worker_profiles: list[str],
    supported_environments: list[str],
    supported_workloads: list[str],
    risk_class: str,
    side_effect_class: str,
    enforcement_tier: str,
    permission_model: dict[str, object],
    cost_model: dict[str, object],
    network_requirements: dict[str, object],
    dependencies: list[str],
    provenance: dict[str, object],
    visibility: str,
    owner_tenant_id: UUID | None,
) -> str:
    payload = {
        "capability_id": capability_id,
        "version": version,
        "category": category,
        "summary": summary,
        "interface_schema_ref": interface_schema_ref,
        "input_schema_ref": input_schema_ref,
        "output_schema_ref": output_schema_ref,
        "implementations": implementations,
        "supported_worker_profiles": supported_worker_profiles,
        "supported_environments": supported_environments,
        "supported_workloads": supported_workloads,
        "risk_class": risk_class,
        "side_effect_class": side_effect_class,
        "enforcement_tier": enforcement_tier,
        "permission_model": permission_model,
        "cost_model": cost_model,
        "network_requirements": network_requirements,
        "dependencies": dependencies,
        "provenance": provenance,
        "visibility": visibility,
        "owner_tenant_id": str(owner_tenant_id) if owner_tenant_id else None,
    }
    return sha256_hex(canonical_json(payload))
