"""VerificationRun lifecycle (Chapter 3.8: "VerificationRun ... Append-only
result").

Unlike `WorkerRun` (Chapter 8.2's "Lifecycle only" -- many transitions, many
UPDATEs over the life of one row), a `VerificationRun` row is durable from
the moment its checks start (`RUNNING`, so a crash mid-verification leaves an
observable, recoverable row per AGENTS.md's "durable identity ... observable
state") and is updated exactly once more, into a single terminal status. Once
terminal, the row is never mutated again -- a later re-verification creates a
new `VerificationRun` row (`sequence + 1` against the same `worker_run_id`)
rather than overwriting this one's result, which is what "Append-only
result" means here.
"""

from __future__ import annotations

from typing import Final

VERIFICATION_RUN_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "RUNNING": frozenset({"PASSED", "FAILED", "PARTIAL", "ERRORED"}),
    "PASSED": frozenset(),
    "FAILED": frozenset(),
    "PARTIAL": frozenset(),
    "ERRORED": frozenset(),
}

TERMINAL_STATES: Final[frozenset[str]] = frozenset(
    {"PASSED", "FAILED", "PARTIAL", "ERRORED"}
)
