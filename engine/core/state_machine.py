"""Generic lifecycle-transition guard shared by modules that own an
optimistically-locked status column (Chapter 3.5). `engine.missions.states`
predates this helper and keeps its own copy — this mission's brief forbids
refactoring `engine.missions` beyond read-only calls — so `engine.environments`
and `engine.workspaces` depend on this shared, independent implementation
instead of importing a sibling module's internals.
"""

from __future__ import annotations

from engine.core.errors import DdeError


def transition(current: str, target: str, table: dict[str, frozenset[str]]) -> str:
    allowed = table.get(current, frozenset())
    if target not in allowed:
        raise DdeError(
            "VERSION_CONFLICT",
            f"Illegal state transition {current} -> {target}",
            details={"from": current, "to": target},
        )
    return target
