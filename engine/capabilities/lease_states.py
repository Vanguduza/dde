"""`CapabilityLease.status`'s real state machine (Chapter 9.2).

Chapter 9.2 literally names: `REQUESTED -> EVALUATING -> GRANTED -> ACTIVE ->
CONSUMED`; `GRANTED|ACTIVE -> EXPIRED | REVOKED`. It does not name a state for
"evaluated and rejected" even though the same section states outright that
"lease denial is a normal control outcome, not an error" -- a real, durable
outcome needs a real, durable status to land in. `DENIED` is this mission's
flagged addition, mirroring exactly how `engine.capabilities.taxonomy`
already flags `certification_status`/`lifecycle_status` as this codebase's
own interpretation where Chapter 9 names a mechanism but not its literal
enum. `EVALUATING -> DENIED` is the only new edge; every edge the chapter
does name is transcribed verbatim.
"""

from __future__ import annotations

from typing import Final

CAPABILITY_LEASE_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "REQUESTED": frozenset({"EVALUATING"}),
    "EVALUATING": frozenset({"GRANTED", "DENIED"}),
    "GRANTED": frozenset({"ACTIVE", "EXPIRED", "REVOKED"}),
    "ACTIVE": frozenset({"CONSUMED", "EXPIRED", "REVOKED"}),
    "DENIED": frozenset(),
    "CONSUMED": frozenset(),
    "EXPIRED": frozenset(),
    "REVOKED": frozenset(),
}

#: A lease in one of these statuses still authorises its bound capability
#: call -- the exact set `require_active`'s enforcement guard accepts.
HELD_LEASE_STATUSES: Final[frozenset[str]] = frozenset({"GRANTED", "ACTIVE"})
