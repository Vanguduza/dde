"""Chapter 3.10 immutable-definition hashing for AcceptanceOracle.

`oracle_version` covers every definition field and excludes the lifecycle/
identity columns (`oracle_id`, `approved_by`, `approved_at`, `created_at`,
`updated_at`) exactly as `engine.routing.hashing.decision_hash` does for
RouteDecision: re-defining an oracle from the same task with the same
observable outcomes produces an identical version even though `oracle_id` is
always fresh.
"""

from __future__ import annotations

from uuid import UUID

from engine.core.hashing import canonical_json, sha256_hex


def oracle_version_hash(
    *,
    tenant_id: UUID,
    project_id: UUID,
    mission_id: UUID,
    task_id: UUID | None,
    scope: str,
    requirement_refs: list[str],
    feature_refs: list[str],
    observable_outcomes: list[dict[str, object]],
    domain_invariants: list[str],
    negative_cases: list[dict[str, object]],
    minimum_confidence: float,
    human_assertions: list[str],
) -> str:
    payload = {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "mission_id": str(mission_id),
        "task_id": None if task_id is None else str(task_id),
        "scope": scope,
        "requirement_refs": requirement_refs,
        "feature_refs": feature_refs,
        "observable_outcomes": observable_outcomes,
        "domain_invariants": domain_invariants,
        "negative_cases": negative_cases,
        "minimum_confidence": minimum_confidence,
        "human_assertions": human_assertions,
    }
    return sha256_hex(canonical_json(payload))
