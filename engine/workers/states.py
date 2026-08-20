"""WorkerRun lifecycle — Chapter 8.2's literal diagram, unlike
`engine.workspaces.states`/`engine.execution.states`' flagged
interpretations:

```
PLANNED -> PREPARING -> READY -> RUNNING -> COMPLETED | FAILED
RUNNING -> CHECKPOINTING -> RUNNING
RUNNING -> PAUSING -> PAUSED -> RESUMING -> RUNNING
RUNNING -> CANCELLING -> CANCELLED
FAILED  -> RECOVERING -> RUNNING | (attempt reroutes / escalates)
```

This mission's one scripted, synchronous certified profile only exercises
`PLANNED -> PREPARING -> READY -> RUNNING -> COMPLETED|FAILED` (Chapter
18.1 Rule 1: "contract-complete but minimal") — the full table is encoded
so the FSM itself is real and complete, not merely the subset a synchronous
backend happens to reach. `RECOVERING`'s "attempt reroutes / escalates"
branch has no single named target state in the chapter's own diagram, so it
is left terminal here: Chapter 12/DDE-024's failure-taxonomy mission owns
turning that prose into a real transition target.
"""

from __future__ import annotations

from typing import Final

WORKER_RUN_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "PLANNED": frozenset({"PREPARING"}),
    "PREPARING": frozenset({"READY", "FAILED"}),
    "READY": frozenset({"RUNNING", "FAILED"}),
    "RUNNING": frozenset(
        {"COMPLETED", "FAILED", "CHECKPOINTING", "PAUSING", "CANCELLING"}
    ),
    "CHECKPOINTING": frozenset({"RUNNING"}),
    "PAUSING": frozenset({"PAUSED"}),
    "PAUSED": frozenset({"RESUMING"}),
    "RESUMING": frozenset({"RUNNING"}),
    "CANCELLING": frozenset({"CANCELLED"}),
    "FAILED": frozenset({"RECOVERING"}),
    "RECOVERING": frozenset({"RUNNING"}),
    "COMPLETED": frozenset(),
    "CANCELLED": frozenset(),
}

#: Chapter 8.2's lifecycle has no terminal state reachable from a fresh
#: `PLANNED` row without at least reaching `PREPARING` — used by
#: `engine.workers.service` to decide whether `ended_at` should be stamped.
TERMINAL_STATES: Final[frozenset[str]] = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
