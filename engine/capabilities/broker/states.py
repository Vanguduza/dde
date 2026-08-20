"""`CredentialHandle.status`'s real state machine.

Chapter 14.3 names the broker's operations (`issue`, `renew`, `revoke`,
`inspect`, `emergency_revoke`) but, unlike Chapter 9.2's literal
`CapabilityLease` enum, never names a literal status vocabulary for the
handle it issues. This mission's flagged interpretation, mirroring
`engine.capabilities.lease_states`' own documented approach to the same gap:
a handle is born `ISSUED` (a credential is either minted successfully or
the request is denied before any row exists -- there is no separate
"pending" state to model, unlike a `CapabilityLease`'s multi-step grant
evaluation). From there it reaches exactly one terminal status: `EXPIRED`
(its own TTL or its lease's elapsed -- observed, not inferred, exactly like
`CapabilityLease`'s own `EXPIRED`), `REVOKED` (Chapter 14.3's `revoke()` /
`emergency_revoke()`), or `SUPERSEDED` (Chapter 14.3's `renew()`: "issues a
replacement" -- the old handle is superseded by a new row, mirroring
`CapabilityDescriptor`'s own supersession pattern, never mutated in place).
"""

from __future__ import annotations

from typing import Final

CREDENTIAL_HANDLE_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "ISSUED": frozenset({"EXPIRED", "REVOKED", "SUPERSEDED"}),
    "EXPIRED": frozenset(),
    "REVOKED": frozenset(),
    "SUPERSEDED": frozenset(),
}

#: A handle in this status is still live -- the only status `verify()`
#: accepts and the only status `issue()`/`renew()`/`revoke()` operate on.
LIVE_HANDLE_STATUSES: Final[frozenset[str]] = frozenset({"ISSUED"})
