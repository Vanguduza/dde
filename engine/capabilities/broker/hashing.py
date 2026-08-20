"""`CommandLedger` request-hash for the broker's two mutating operations
(`issue`, `renew`). Chapter 3.10 does not list `CredentialHandle` among its
named content-hashed immutable definitions -- unlike `CapabilityLease`/
`CapabilityDescriptor`, a handle's entire content is derived from its lease
plus policy, not independently re-suppliable -- so this hash exists only for
`engine.events.idempotency.CommandLedger`'s own narrower purpose: detecting
a caller that reuses one `idempotency_key` for a logically different
request (Chapter 12.5), not for re-finding an existing row by content.
"""

from __future__ import annotations

from uuid import UUID

from engine.core.hashing import canonical_json, sha256_hex


def issuance_request_hash(*, lease_id: UUID, requested_by: str) -> str:
    return sha256_hex(
        canonical_json({"lease_id": str(lease_id), "requested_by": requested_by})
    )


def renewal_request_hash(*, handle_id: UUID, requested_by: str) -> str:
    return sha256_hex(
        canonical_json({"handle_id": str(handle_id), "requested_by": requested_by})
    )
