"""Lifecycle tables for Chapter 10's two objects.

`WriteScopeLease` (Chapter 10.3's literal enum: `RESERVED, ACTIVE, RELEASED,
EXPIRED`) is "Status only" mutable per Chapter 3.8 -- reserved by the Task
Planner before scheduling, activated once a run actually starts, released
(or expired) once the task attempt that held it is done with it.

`IntegrationProposal` (Chapter 10.4's literal enum: `QUEUED, REBASING,
VALIDATING, VERIFYING, MERGED, CONFLICT, REJECTED, SUPERSEDED`) walks the
queue algorithm's own step order. `QUEUED -> VALIDATING` is the fast path
when `base_revision` already equals the mission branch head (10.4 step 2's
rebase is conditional); `SUPERSEDED` is a valid terminal Chapter 10.4 names
but this mission's Stage 1 scope never drives a proposal into it (no
replan-triggered supersession exists yet)."""

from __future__ import annotations

from typing import Final

WRITE_SCOPE_LEASE_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "RESERVED": frozenset({"ACTIVE", "RELEASED", "EXPIRED"}),
    "ACTIVE": frozenset({"RELEASED", "EXPIRED"}),
    "RELEASED": frozenset(),
    "EXPIRED": frozenset(),
}

INTEGRATION_PROPOSAL_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "QUEUED": frozenset({"REBASING", "VALIDATING", "SUPERSEDED"}),
    "REBASING": frozenset({"VALIDATING", "CONFLICT"}),
    "VALIDATING": frozenset({"VERIFYING", "REJECTED"}),
    "VERIFYING": frozenset({"MERGED", "REJECTED", "CONFLICT"}),
    "MERGED": frozenset(),
    "CONFLICT": frozenset(),
    "REJECTED": frozenset(),
    "SUPERSEDED": frozenset(),
}

TERMINAL_PROPOSAL_STATES: Final[frozenset[str]] = frozenset(
    {"MERGED", "CONFLICT", "REJECTED", "SUPERSEDED"}
)
