"""Chapter 13.1 / 13.2 / 13.4 status machines."""

from __future__ import annotations

from typing import Final

APPROVAL_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "REQUESTED": frozenset(
        {"UNDER_REVIEW", "APPROVED", "REJECTED", "EXPIRED", "WITHDRAWN"}
    ),
    "UNDER_REVIEW": frozenset({"APPROVED", "REJECTED", "EXPIRED", "WITHDRAWN"}),
    "APPROVED": frozenset({"EXPIRED", "WITHDRAWN"}),
    "REJECTED": frozenset(),
    "EXPIRED": frozenset(),
    "WITHDRAWN": frozenset(),
}

STANDING_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "ACTIVE": frozenset({"REVOKED", "EXPIRED"}),
    "REVOKED": frozenset(),
    "EXPIRED": frozenset(),
}

ATTENTION_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "OPEN": frozenset({"ACKNOWLEDGED", "CLEARED"}),
    "ACKNOWLEDGED": frozenset({"CLEARED"}),
    "CLEARED": frozenset(),
}
