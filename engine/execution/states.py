"""ExecutionPlan lifecycle.

Chapter 7.1 gives ExecutionPlan `created_at/approved_at/started_at/ended_at`
timestamp columns and a bare `status` field, but — unlike Chapter 7.3's
explicit "States:" line for ExecutionEnvironment — never spells out
`status`'s enum. **This is a flagged interpretation, not a chapter
quotation**: the four states below are the minimal sequence consistent with
those four timestamp columns (one state transition per timestamp) and with
Chapter 3.9's creation order (step 7: "ExecutionPlan validated and
committed"), and with Chapter 3.8 ("Definition immutable; status mutable").
"""

from __future__ import annotations

from typing import Final

EXECUTION_PLAN_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "PLANNED": frozenset({"APPROVED", "FAILED"}),
    "APPROVED": frozenset({"ACTIVE", "FAILED"}),
    "ACTIVE": frozenset({"COMPLETED", "FAILED"}),
    "COMPLETED": frozenset(),
    "FAILED": frozenset(),
}
