"""Chapter 4.3 registry hashing.

`template_version` covers every definition field and excludes the
identity/lifecycle columns (`template_id`, `status`, `created_at`,
`updated_at`) exactly as `engine.invariants.hashing.
definition_version_hash` does for DomainInvariant: re-registering a
template from the same definition fields produces an identical version
even though `template_id` is always fresh, which is what makes
`register()` idempotent (Chapter 3.10: immutable definitions are
content-addressed).

`draft_provenance_key` is the caller-facing identity of one model-
assisted proposal: the same mission proposed from the same adapter under
the same policy version hashes to one key, so re-submitting an identical
draft replays the first row instead of minting a twin (the uniqueness
the `plan_drafts` table enforces).
"""

from __future__ import annotations

from uuid import UUID

from engine.contracts.mission_template import TemplateEdge, TemplateNode
from engine.core.hashing import canonical_json, sha256_hex


def template_version_hash(
    *,
    tenant_id: UUID,
    project_id: UUID,
    template_key: str,
    description: str,
    nodes: list[TemplateNode],
    edges: list[TemplateEdge],
    planner_policy_version: str,
) -> str:
    payload = {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "template_key": template_key,
        "description": description,
        "nodes": [node.model_dump() for node in nodes],
        "edges": [edge.model_dump() for edge in edges],
        "planner_policy_version": planner_policy_version,
        "schema_version": 1,
    }
    return sha256_hex(canonical_json(payload))


def draft_provenance_key(
    *,
    tenant_id: UUID,
    project_id: UUID,
    mission_id: UUID,
    origin: str,
    adapter_ref: str | None,
    origin_policy_version: str,
    nodes: list[object],
) -> str:
    """Stable identity of one draft submission. Deliberately excludes the
    node payloads' ordering but includes their content via the canonical
    dump of each node dict supplied by the service layer."""
    payload = {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "mission_id": str(mission_id),
        "origin": origin,
        "adapter_ref": adapter_ref,
        "origin_policy_version": origin_policy_version,
        "schema_version": 1,
    }
    return sha256_hex(canonical_json(payload))
