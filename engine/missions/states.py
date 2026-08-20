"""Mission and task state machines (Chapters 4.8, 4.9, 12.6, 15.4)."""

from __future__ import annotations

from typing import Final

from engine.core.errors import DdeError

MISSION_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "CREATED": frozenset({"ACTIVE", "CANCELLED"}),
    "ACTIVE": frozenset({"PARTIAL", "PAUSED", "COMPLETED", "FAILED", "CANCELLED"}),
    "PARTIAL": frozenset({"ACTIVE", "PAUSED", "COMPLETED", "FAILED", "CANCELLED"}),
    "PAUSED": frozenset({"ACTIVE", "PARTIAL", "CANCELLED", "FAILED"}),
    "COMPLETED": frozenset(),
    "FAILED": frozenset(),
    "CANCELLED": frozenset(),
}

GRAPH_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "DRAFT": frozenset({"VALIDATING", "REJECTED"}),
    "VALIDATING": frozenset({"APPROVED", "REJECTED"}),
    "APPROVED": frozenset({"ACTIVE"}),
    "ACTIVE": frozenset({"AMENDING", "REPLANNING", "COMPLETED", "SUPERSEDED"}),
    # DDE-007 flagged divergence: Chapter 4.8's literal diagram only shows
    # `ACTIVE -> AMENDING -> ACTIVE`. Rule 4.5.4 ("accepting an amendment
    # produces version+1; the prior version is retained; supersedes_id
    # links them") is incompatible with leaving the prior row ACTIVE once a
    # new version also becomes ACTIVE — two ACTIVE TaskGraph rows for one
    # mission would be a second source of truth for "which graph is in
    # force". Smallest conservative resolution, symmetric with the
    # REPLANNING path's explicit "this one SUPERSEDED": the amended-away
    # version's terminal state is SUPERSEDED.
    "AMENDING": frozenset({"ACTIVE", "SUPERSEDED"}),
    "REPLANNING": frozenset({"SUPERSEDED"}),
    "COMPLETED": frozenset(),
    "REJECTED": frozenset(),
    "SUPERSEDED": frozenset(),
}

_TASK_ANY = frozenset({"BLOCKED_ON_DECISION", "SUPERSEDED", "RETIRED"})

TASK_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "CREATED": frozenset({"BLOCKED", "READY"}) | _TASK_ANY,
    "BLOCKED": frozenset({"READY"}) | _TASK_ANY,
    "READY": frozenset({"CONTEXT_READY", "BLOCKED"}) | _TASK_ANY,
    "CONTEXT_READY": frozenset({"ROUTED"}) | _TASK_ANY,
    "ROUTED": frozenset({"PLANNED"}) | _TASK_ANY,
    "PLANNED": frozenset({"EXECUTING"}) | _TASK_ANY,
    "EXECUTING": frozenset({"VERIFYING", "RETRYING", "REROUTING"}) | _TASK_ANY,
    "RETRYING": frozenset({"PLANNED"}) | _TASK_ANY,
    "REROUTING": frozenset({"ROUTED"}) | _TASK_ANY,
    "VERIFYING": frozenset({"INTEGRATING", "REPAIR_REQUIRED"}) | _TASK_ANY,
    "REPAIR_REQUIRED": frozenset({"PLANNED"}) | _TASK_ANY,
    "INTEGRATING": frozenset({"COMPLETED", "MERGE_CONFLICT"}) | _TASK_ANY,
    "MERGE_CONFLICT": frozenset({"PLANNED"}) | _TASK_ANY,
    "BLOCKED_ON_DECISION": frozenset({"READY"}) | _TASK_ANY,
    "COMPLETED": frozenset({"SUPERSEDED", "RETIRED"}),
    "SUPERSEDED": frozenset(),
    "RETIRED": frozenset(),
}

TERMINAL_MISSION = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
IN_FLIGHT_TASK = frozenset(
    {
        "CONTEXT_READY",
        "ROUTED",
        "PLANNED",
        "EXECUTING",
        "VERIFYING",
        "INTEGRATING",
        "RETRYING",
        "REROUTING",
        "REPAIR_REQUIRED",
        "MERGE_CONFLICT",
    }
)


def transition(current: str, target: str, table: dict[str, frozenset[str]]) -> str:
    allowed = table.get(current, frozenset())
    if target not in allowed:
        raise DdeError(
            "VERSION_CONFLICT",
            f"Illegal state transition {current} → {target}",
            details={"from": current, "to": target},
        )
    return target
