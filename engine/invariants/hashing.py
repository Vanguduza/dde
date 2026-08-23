"""Chapter 11.5 definition-version hashing.

`definition_version` covers every definition field and excludes the
identity/lifecycle columns (`invariant_id`, `status`, `created_at`,
`updated_at`) exactly as `engine.verification.hashing.oracle_version_hash`
does for AcceptanceOracle: re-declaring an invariant from the same
definition fields produces an identical version even though `invariant_id`
is always fresh, which is what makes `define()` idempotent (Chapter 3.10:
immutable definitions are content-addressed).
"""

from __future__ import annotations

from uuid import UUID

from engine.contracts.domain_invariant import PredicateSpec
from engine.core.hashing import canonical_json, sha256_hex


def definition_version_hash(
    *,
    tenant_id: UUID,
    project_id: UUID,
    name: str,
    description: str,
    predicate: PredicateSpec,
    financial_state: bool,
    required_fixture_class: str,
    product_env_class: str,
) -> str:
    payload = {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "name": name,
        "description": description,
        "predicate": predicate.model_dump(),
        "financial_state": financial_state,
        "required_fixture_class": required_fixture_class,
        "product_env_class": product_env_class,
        "schema_version": 1,
    }
    return sha256_hex(canonical_json(payload))
