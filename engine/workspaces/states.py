"""Workspace lifecycle.

Chapter 7.5 defines Workspace only by its operation surface — `create()`,
`read()`, `write()`, `execute()`, `capture_revision()`, `snapshot()`,
`cleanup()` — and never spells out named lifecycle states the way Chapter
7.3's "States:" line does for ExecutionEnvironment. **This is a flagged
interpretation, not a chapter quotation**: the states below are the minimal
set that makes those seven operations independently observable and
recoverable (Chapter 19.1's state-transition/recovery test types need a real
`status` column to assert against), chosen to mirror ExecutionEnvironment's
own `PROVISIONING -> READY -> ... -> RETIRED` shape as closely as a
worktree's actual operations allow.
"""

from __future__ import annotations

from typing import Final

WORKSPACE_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "PROVISIONING": frozenset({"READY", "FAILED"}),
    "READY": frozenset({"IN_USE", "CLEANED_UP", "FAILED"}),
    "IN_USE": frozenset({"READY", "CLEANED_UP", "FAILED"}),
    "CLEANED_UP": frozenset(),
    "FAILED": frozenset({"CLEANED_UP"}),
}
