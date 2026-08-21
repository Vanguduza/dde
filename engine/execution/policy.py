"""Declared Stage 1 execution policy table — the in-code equivalent of
Chapter 6.2's approach applied to Chapter 7.1's "compute budgets" planner
step: a small, versioned, deterministic lookup rather than a learned cost
model (no telemetry exists yet to fit one against — Chapter 6.5/DDE-035).

`EFFORT_BUDGETS` derives `resource_budget`/`time_budget`/`token_budget` from
`Task.estimated_effort` (`xs`/`s`/`m`/`l`) — a real, already-persisted Task
field (Chapter 4's `Task` contract), not an invented one. Values are
conservative, explicit constants for a `local_process` backend running this
mission's own test/verification commands; they are not calibrated against
real worker cost data because none exists at Stage 1.

`enforcement_tier = "audit_only"` is Chapter 7.2's own literal value for
"local development and simulation" — the only tier compatible with this
mission's scope, since Chapter 7.2's T1/T2 tiers both require infrastructure
this mission explicitly defers: T1 needs the capability gateway (Chapter 9,
DDE-016/017), T2 needs container/microVM containment (DDE-018). Chapter
7.2 restricts `audit_only` to `environment_class = "development"`
(rejected elsewhere by configuration validation, Chapter 13.7 — which does
not exist yet); this module pins `environment_class = "development"` for
every plan for exactly that reason, flagged as a Stage 1 simplification
pending a real target-class field on Task/RouteDecision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

POLICY_VERSION = "execution-planner-v1"

ENFORCEMENT_TIER: Final = "audit_only"
ENVIRONMENT_CLASS: Final = "development"
ENVIRONMENT_TYPE: Final = "local"


@dataclass(frozen=True)
class EffortBudget:
    cpu_seconds: int
    memory_mb: int
    wall_clock_seconds: int
    max_tokens: int


EFFORT_BUDGETS: dict[str, EffortBudget] = {
    "xs": EffortBudget(
        cpu_seconds=60, memory_mb=512, wall_clock_seconds=120, max_tokens=20_000
    ),
    "s": EffortBudget(
        cpu_seconds=300, memory_mb=1024, wall_clock_seconds=600, max_tokens=60_000
    ),
    "m": EffortBudget(
        cpu_seconds=900, memory_mb=2048, wall_clock_seconds=1800, max_tokens=150_000
    ),
    "l": EffortBudget(
        cpu_seconds=3600, memory_mb=4096, wall_clock_seconds=7200, max_tokens=400_000
    ),
}


def budget_for_effort(estimated_effort: str) -> EffortBudget:
    return EFFORT_BUDGETS[estimated_effort]


def checkpoint_policy_json() -> dict[str, object]:
    return {
        "enabled": True,
        "engine": "engine.recovery.checkpoint_service",
        "reason": "Chapter 12.1 reconstructible continuation contract (DDE-023)",
    }


def retry_policy_json() -> dict[str, object]:
    return {
        "max_attempts": 2,
        "matrix_version": "recovery-matrix-v1",
        "engine": "engine.recovery.matrix",
        "reason": (
            "Chapter 12.3 recovery matrix (DDE-024): dispatch on failure "
            "class; WORKER_FAILURE allows one recover then reroute"
        ),
    }


def escalation_policy_json() -> dict[str, object]:
    return {
        "on_failure": "escalate_to_human",
        "reason": (
            "Chapter 13's approvals/autonomy-budget engine is deferred to "
            "DDE-026 (Stage 3)"
        ),
    }
