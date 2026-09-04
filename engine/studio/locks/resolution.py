"""DDE-069 effective-lock resolution -- pure, so the rules are testable.

A lock covers its `scope_key` and everything contained beneath it, so
locking a screen locks its regions without a row per descendant. Which
lock kinds bite which mutation operations is a table rather than
scattered conditionals, because "does this edit cross a lock?" must have
exactly one answer regardless of which UI affordance asked.

The effective-lock hash is what lets a mutation planned a moment ago
notice that the lock set changed underneath it: it goes into the
mutation's preconditions and is re-derived at apply time.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from engine.contracts.frontend_lock import FrontendLock

#: Which mutation operations each lock kind refuses. A kind absent from a
#: row does not refuse that operation -- a STYLE lock does not stop a
#: component being moved, and a STRUCTURE lock does not stop a colour
#: token changing. Collapsing these into one "locked" boolean is what
#: makes people disable locks wholesale.
LOCK_COVERAGE: Final[dict[str, frozenset[str]]] = {
    "GLOBAL_DESIGN": frozenset(
        {
            "ADD",
            "REMOVE",
            "MOVE",
            "REORDER",
            "REPLACE",
            "RESTYLE",
            "SET_PROPERTY",
            "SET_BEHAVIOUR",
            "SET_RESPONSIVE",
        }
    ),
    "SCREEN": frozenset(
        {
            "ADD",
            "REMOVE",
            "MOVE",
            "REORDER",
            "REPLACE",
            "RESTYLE",
            "SET_PROPERTY",
            "SET_BEHAVIOUR",
            "SET_RESPONSIVE",
        }
    ),
    "SECTION": frozenset(
        {"ADD", "REMOVE", "MOVE", "REORDER", "REPLACE", "SET_PROPERTY"}
    ),
    "COMPONENT": frozenset({"REMOVE", "REPLACE", "MOVE", "SET_PROPERTY"}),
    "STRUCTURE": frozenset({"ADD", "REMOVE", "MOVE", "REORDER", "REPLACE"}),
    "STYLE": frozenset({"RESTYLE", "SET_PROPERTY"}),
    "BEHAVIOUR": frozenset({"SET_BEHAVIOUR"}),
    "CONTENT": frozenset({"SET_PROPERTY", "REPLACE"}),
    "TOKEN": frozenset({"RESTYLE", "SET_PROPERTY"}),
}

GLOBAL_SCOPE: Final = "*"


@dataclass(frozen=True)
class LockDecision:
    """Whether a mutation may proceed, and which locks said otherwise."""

    allowed: bool
    blocking: tuple[FrontendLock, ...]

    @property
    def reason(self) -> str | None:
        if self.allowed:
            return None
        return "; ".join(
            f"{lock.lock_kind} lock on {lock.scope_key}: {lock.reason}"
            for lock in self.blocking
        )


def covers_key(scope_key: str, target_key: str) -> bool:
    """Does a lock at `scope_key` cover `target_key`?

    Containment is by path prefix on the PXG key grammar. The segment
    boundary check matters: `screens/checkout` must not be treated as
    covering `screens/checkout-archive`.
    """
    if scope_key == GLOBAL_SCOPE:
        return True
    if scope_key == target_key:
        return True
    for separator in ("/", "#"):
        if target_key.startswith(scope_key + separator):
            return True
    return False


def evaluate(
    locks: Iterable[FrontendLock], *, target_key: str, operation: str
) -> LockDecision:
    """Decide one mutation against the active lock set."""
    blocking = tuple(
        lock
        for lock in locks
        if lock.status == "ACTIVE"
        and covers_key(lock.scope_key, target_key)
        and operation in LOCK_COVERAGE.get(lock.lock_kind, frozenset())
    )
    return LockDecision(allowed=not blocking, blocking=blocking)


def effective_lock_hash(locks: Sequence[FrontendLock]) -> str:
    """Stable hash over the ACTIVE lock set.

    Recorded in a mutation's preconditions so an apply can notice the
    locks changed after the plan was made. Released locks are excluded:
    releasing a lock widens what is permitted, and a plan made under the
    stricter set stays valid.
    """
    payload = sorted(
        (lock.lock_kind, lock.scope_key, str(lock.lock_id))
        for lock in locks
        if lock.status == "ACTIVE"
    )
    encoded = json.dumps(payload, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
