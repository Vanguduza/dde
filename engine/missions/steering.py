"""EDR-0019 Epic A safe-boundary mission steering.

A steer is acknowledged immediately and executed at a boundary the active writer
chooses to reach. It neither kills work in flight nor queues behind autonomous
dispatch. A barrier bounds *new* conflicting lease claims only; it never revokes
a lease already held, and a read-only owner question takes no barrier at all so
it cannot serialize writers.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from engine.core.errors import DdeError

RECEIVED = "RECEIVED"
ACKNOWLEDGED = "ACKNOWLEDGED"
BARRIER_SET = "BARRIER_SET"
WAITING_FOR_SAFE_BOUNDARY = "WAITING_FOR_SAFE_BOUNDARY"
SAFE_BOUNDARY_REACHED = "SAFE_BOUNDARY_REACHED"
AUTHORITY_RECONCILED = "AUTHORITY_RECONCILED"
EXECUTING = "EXECUTING"
VERIFIED = "VERIFIED"
COMPLETE = "COMPLETE"
FAILED = "FAILED"
BLOCKED = "BLOCKED"
SUPERSEDED = "SUPERSEDED"

STEER_TRANSITIONS: MappingProxyType[str, frozenset[str]] = MappingProxyType(
    {
        RECEIVED: frozenset({ACKNOWLEDGED, BLOCKED, SUPERSEDED}),
        # A read-only or non-material steer skips the barrier entirely.
        ACKNOWLEDGED: frozenset({BARRIER_SET, EXECUTING, BLOCKED, SUPERSEDED}),
        BARRIER_SET: frozenset(
            {WAITING_FOR_SAFE_BOUNDARY, SAFE_BOUNDARY_REACHED, BLOCKED, SUPERSEDED}
        ),
        WAITING_FOR_SAFE_BOUNDARY: frozenset(
            {SAFE_BOUNDARY_REACHED, BLOCKED, SUPERSEDED, FAILED}
        ),
        SAFE_BOUNDARY_REACHED: frozenset({AUTHORITY_RECONCILED, BLOCKED, SUPERSEDED}),
        AUTHORITY_RECONCILED: frozenset({EXECUTING, BLOCKED, SUPERSEDED}),
        EXECUTING: frozenset({VERIFIED, FAILED, BLOCKED, SUPERSEDED}),
        VERIFIED: frozenset({COMPLETE, FAILED}),
        COMPLETE: frozenset(),
        FAILED: frozenset({SUPERSEDED}),
        BLOCKED: frozenset({ACKNOWLEDGED, SUPERSEDED, FAILED}),
        SUPERSEDED: frozenset(),
    }
)

#: Boundaries at which an active writer may hand control to a steer.
SAFE_BOUNDARIES = frozenset(
    {
        "COMMITTED_CHECKPOINT",
        "CLEAN_STAGED_CHECKPOINT",
        "ROLLBACK_CHECKPOINT",
        "VERIFIER_COMPLETE",
        "NO_ACTIVE_WRITER",
    }
)

#: Lease kinds a barrier may block from being newly claimed.
BLOCKABLE_LEASE_KINDS = frozenset({"WORKSPACE", "WRITE_SCOPE", "CAPABILITY"})


@dataclass(frozen=True, slots=True)
class ActiveWriter:
    writer_ref: str
    write_scope: tuple[str, ...]
    at_boundary: str | None = None


@dataclass(frozen=True, slots=True)
class SteerRequest:
    steer_id: str
    authority_class: str
    read_only: bool
    material: bool
    write_ownership_scope: tuple[str, ...]


def require_legal_transition(from_state: str, to_state: str) -> None:
    allowed = STEER_TRANSITIONS.get(from_state)
    if allowed is None or to_state not in allowed:
        raise DdeError(
            "POLICY_DENIED",
            f"illegal steer transition {from_state} -> {to_state}",
            retryable=False,
            details={"from_state": from_state, "to_state": to_state},
        )


def require_authorized(request: SteerRequest) -> None:
    """NO_AUTHORITY is a read-only question; it may never execute a change."""
    if request.authority_class == "NO_AUTHORITY" and not request.read_only:
        raise DdeError(
            "FORBIDDEN",
            "a NO_AUTHORITY steer may only ask a read-only question",
            retryable=False,
            details={"steer_id": request.steer_id},
        )


def needs_barrier(request: SteerRequest) -> bool:
    """Only a material, non-read-only steer takes a barrier.

    This is what keeps owner status questions from serializing writers.
    """
    require_authorized(request)
    return request.material and not request.read_only


def scopes_conflict(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    """Path-prefix overlap in either direction is a conflict."""
    for a in left:
        for b in right:
            if a == b or a.startswith(f"{b}/") or b.startswith(f"{a}/"):
                return True
    return False


def blocks_new_claim(
    *, barrier_scope: tuple[str, ...], lease_kind: str, requested_scope: tuple[str, ...]
) -> bool:
    """A barrier blocks new conflicting claims; it never revokes a held lease."""
    if lease_kind not in BLOCKABLE_LEASE_KINDS:
        return False
    return scopes_conflict(barrier_scope, requested_scope)


def awaited_writers(
    *, barrier_scope: tuple[str, ...], active: tuple[ActiveWriter, ...]
) -> tuple[ActiveWriter, ...]:
    """Writers the steer must wait for, i.e. those still short of a boundary."""
    return tuple(
        writer
        for writer in active
        if scopes_conflict(barrier_scope, writer.write_scope)
        and writer.at_boundary not in SAFE_BOUNDARIES
    )


def barrier_is_satisfied(
    *, barrier_scope: tuple[str, ...], active: tuple[ActiveWriter, ...]
) -> bool:
    return not awaited_writers(barrier_scope=barrier_scope, active=active)


def require_safe_boundary(boundary_kind: str) -> None:
    if boundary_kind not in SAFE_BOUNDARIES:
        raise DdeError(
            "POLICY_DENIED",
            f"{boundary_kind} is not a safe boundary for a steer",
            retryable=False,
        )


def next_state_after_acknowledge(request: SteerRequest) -> str:
    return BARRIER_SET if needs_barrier(request) else EXECUTING
