"""ClientSession status model (Chapter 15.1)."""

from __future__ import annotations

from typing import Final

from engine.core.errors import DdeError

SESSION_STATUSES: Final[frozenset[str]] = frozenset({"ACTIVE", "CLOSED", "EXPIRED"})

#: A session is ACTIVE from open until it is closed or expired; neither
#: CLOSED nor EXPIRED is reversible, so a client must open a fresh session.
SESSION_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "ACTIVE": frozenset({"CLOSED", "EXPIRED"}),
}


def transition(current: str, target: str) -> str:
    """Return `target` only if `current -> target` is a legal lifecycle move."""
    allowed = SESSION_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise DdeError(
            "SESSION_EXPIRED",
            f"Session cannot transition from {current} to {target}",
            details={"from": current, "to": target},
        )
    return target
