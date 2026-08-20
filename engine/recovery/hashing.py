"""`ExternalEffect.request_hash`/`response_hash` helpers -- mirrors
`engine.capabilities.broker.hashing`'s pattern exactly: canonical-JSON-then-
SHA-256, deterministic, no timestamps in the hashed payload.

`request_hash` doubles as both the column value Chapter 12.4 names AND the
`request_hash` `engine.events.idempotency.CommandLedger.begin` uses to
detect a caller reusing one `idempotency_key` for a logically different
request (Chapter 12.5) -- the same dual role `engine.capabilities.
lease_hashing.lease_hash` already plays for `CapabilityLease.lease_hash`.

`response_hash` exists so a real provider response (subprocess stdout/
stderr, a git command's output) is journaled as a digest, never as
unbounded raw text on the durable row itself -- `ExternalEffect` has no
"response body" column, matching Chapter 12.4's own field list exactly.
"""

from __future__ import annotations

from uuid import UUID

from engine.core.hashing import canonical_json, sha256_hex


def effect_request_hash(
    *,
    worker_run_id: UUID,
    capability_lease_id: UUID,
    target_system: str,
    target_resource: str,
    operation: str,
) -> str:
    return sha256_hex(
        canonical_json(
            {
                "worker_run_id": str(worker_run_id),
                "capability_lease_id": str(capability_lease_id),
                "target_system": target_system,
                "target_resource": target_resource,
                "operation": operation,
            }
        )
    )


def effect_response_hash(payload: dict[str, object]) -> str:
    return sha256_hex(canonical_json(payload))


def mutation_scope_token(
    *, target_system: str, target_resource: str, operation: str
) -> str:
    """Logical mutation identity stored on Checkpoint.do_not_repeat.

    An idempotency key is caller-chosen and would be bypassed by a new
    WorkerRun; this token is not.
    """
    return f"{target_system}:{target_resource}:{operation}"


def checkpoint_integrity_hash(payload: dict[str, object]) -> str:
    """Chapter 12.1 integrity_hash -- reconstructible fields only, no
    identity/timestamps, so a later identical continuation hashes the same.
    """
    return sha256_hex(canonical_json(payload))
