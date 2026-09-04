"""DDE-069 candidate lifecycle -- a governed state machine, not booleans.

The candidate strip in the golden UI shows real state. That is only
possible if state transitions are governed centrally: a frontend that can
set `verified = true` on its own is a frontend that can show a verified
badge for an unverified candidate.

The transition table below is the whole authority. Anything not in it is
refused, so a new code path cannot invent a shortcut from EDITING to
PROMOTED without that shortcut being visible here.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from engine.core.errors import DdeError


class CandidateState(StrEnum):
    REQUESTED = "REQUESTED"
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    MATERIALIZING = "MATERIALIZING"
    RENDERING = "RENDERING"
    READY = "READY"
    EDITING = "EDITING"
    DIRTY = "DIRTY"
    VERIFYING = "VERIFYING"
    FAILED = "FAILED"
    REPAIRABLE = "REPAIRABLE"
    REPAIRING = "REPAIRING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    PROMOTABLE = "PROMOTABLE"
    PROMOTING = "PROMOTING"
    PROMOTED = "PROMOTED"
    SUPERSEDED = "SUPERSEDED"
    ERRORED = "ERRORED"


#: States from which nothing further may happen.
TERMINAL: Final[frozenset[CandidateState]] = frozenset(
    {
        CandidateState.PROMOTED,
        CandidateState.REJECTED,
        CandidateState.SUPERSEDED,
    }
)

#: States in which a candidate may accept mutations. Note that VERIFIED
#: is included and deliberately drops back to DIRTY on edit: a verified
#: candidate that is then edited is no longer verified, and letting it
#: keep the badge is how an unverified change reaches promotion.
MUTABLE: Final[frozenset[CandidateState]] = frozenset(
    {
        CandidateState.READY,
        CandidateState.EDITING,
        CandidateState.DIRTY,
        CandidateState.VERIFIED,
        CandidateState.PROMOTABLE,
        CandidateState.REPAIRABLE,
    }
)

ALLOWED: Final[dict[CandidateState, frozenset[CandidateState]]] = {
    CandidateState.REQUESTED: frozenset(
        {CandidateState.GENERATING, CandidateState.REJECTED, CandidateState.ERRORED}
    ),
    CandidateState.GENERATING: frozenset(
        {CandidateState.GENERATED, CandidateState.FAILED, CandidateState.ERRORED}
    ),
    CandidateState.GENERATED: frozenset(
        {
            CandidateState.MATERIALIZING,
            CandidateState.REJECTED,
            CandidateState.ERRORED,
        }
    ),
    CandidateState.MATERIALIZING: frozenset(
        {CandidateState.RENDERING, CandidateState.FAILED, CandidateState.ERRORED}
    ),
    CandidateState.RENDERING: frozenset(
        {CandidateState.READY, CandidateState.FAILED, CandidateState.ERRORED}
    ),
    CandidateState.READY: frozenset(
        {
            CandidateState.EDITING,
            # A mutation applied to a clean, rendered candidate leaves it
            # with unrendered changes: READY -> DIRTY is the ordinary edit
            # path, not an exceptional one.
            CandidateState.DIRTY,
            CandidateState.VERIFYING,
            CandidateState.REJECTED,
            CandidateState.SUPERSEDED,
            CandidateState.BLOCKED,
            CandidateState.ERRORED,
        }
    ),
    CandidateState.EDITING: frozenset(
        {CandidateState.DIRTY, CandidateState.READY, CandidateState.ERRORED}
    ),
    CandidateState.DIRTY: frozenset(
        {
            CandidateState.RENDERING,
            CandidateState.EDITING,
            CandidateState.VERIFYING,
            CandidateState.REJECTED,
            CandidateState.SUPERSEDED,
            CandidateState.ERRORED,
        }
    ),
    CandidateState.VERIFYING: frozenset(
        {
            CandidateState.VERIFIED,
            CandidateState.FAILED,
            CandidateState.BLOCKED,
            CandidateState.ERRORED,
        }
    ),
    CandidateState.FAILED: frozenset(
        {
            CandidateState.REPAIRABLE,
            CandidateState.REJECTED,
            CandidateState.SUPERSEDED,
            CandidateState.ERRORED,
        }
    ),
    CandidateState.REPAIRABLE: frozenset(
        {
            CandidateState.REPAIRING,
            CandidateState.EDITING,
            CandidateState.DIRTY,
            CandidateState.REJECTED,
            CandidateState.ERRORED,
        }
    ),
    CandidateState.REPAIRING: frozenset(
        {CandidateState.RENDERING, CandidateState.FAILED, CandidateState.ERRORED}
    ),
    CandidateState.VERIFIED: frozenset(
        {
            CandidateState.PROMOTABLE,
            CandidateState.EDITING,
            CandidateState.DIRTY,
            CandidateState.BLOCKED,
            CandidateState.SUPERSEDED,
            CandidateState.REJECTED,
            CandidateState.ERRORED,
        }
    ),
    CandidateState.BLOCKED: frozenset(
        {
            CandidateState.VERIFYING,
            CandidateState.EDITING,
            CandidateState.REJECTED,
            CandidateState.SUPERSEDED,
            CandidateState.ERRORED,
        }
    ),
    # PROMOTABLE cannot reach PROMOTED directly: PROMOTING is where the
    # gate runs, so there is no state pair that skips it.
    CandidateState.PROMOTABLE: frozenset(
        {
            CandidateState.PROMOTING,
            CandidateState.DIRTY,
            CandidateState.EDITING,
            CandidateState.BLOCKED,
            CandidateState.SUPERSEDED,
            CandidateState.REJECTED,
            CandidateState.ERRORED,
        }
    ),
    CandidateState.PROMOTING: frozenset(
        {
            CandidateState.PROMOTED,
            CandidateState.BLOCKED,
            CandidateState.FAILED,
            CandidateState.ERRORED,
        }
    ),
    CandidateState.PROMOTED: frozenset(),
    CandidateState.REJECTED: frozenset(),
    CandidateState.SUPERSEDED: frozenset(),
    CandidateState.ERRORED: frozenset(
        {CandidateState.REJECTED, CandidateState.SUPERSEDED}
    ),
}


def assert_transition(current: CandidateState, target: CandidateState) -> None:
    """Refuse any transition the table does not permit."""
    if target == current:
        raise DdeError(
            "VALIDATION_FAILED",
            "a candidate transition must change state",
            retryable=False,
            details={"state": current.value},
        )
    if target not in ALLOWED[current]:
        raise DdeError(
            "POLICY_DENIED",
            "illegal candidate state transition",
            retryable=False,
            details={
                "from": current.value,
                "to": target.value,
                "allowed": sorted(item.value for item in ALLOWED[current]),
            },
        )


def is_mutable(state: CandidateState) -> bool:
    return state in MUTABLE


def state_after_mutation(state: CandidateState) -> CandidateState:
    """Where a candidate lands once a mutation is applied.

    A VERIFIED or PROMOTABLE candidate drops back to DIRTY: the evidence
    described the code before the edit, so continuing to display it would
    be a fabricated verdict.
    """
    if state in (
        CandidateState.VERIFIED,
        CandidateState.PROMOTABLE,
        CandidateState.READY,
        CandidateState.REPAIRABLE,
    ):
        return CandidateState.DIRTY
    if state is CandidateState.EDITING:
        return CandidateState.DIRTY
    return state
