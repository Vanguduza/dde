"""In-process value objects for the Chapter 6.5 real-telemetry engine
(DDE-035).

`schemas/objects/routing_decision_outcome.json` is the durable contract
this module owns (Chapter 3.8); `TelemetryOutcome` is the pure,
input-dependent computation output before it is stamped with identity and
persisted as a `RoutingDecisionOutcome` row.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: Chapter 6.5 fields this Stage 1 slice cannot populate from a real
#: signal: `WorkerRun.usage_record_id` points to a table (`UsageRecord`)
#: no writer in this codebase produces yet, so "actual token/tool cost"
#: cannot be read from anywhere real. Named on every persisted row rather
#: than silently omitted or defaulted to a fabricated number.
ACTUAL_COST_GAP_DISCLOSED = (
    "actual_token_cost/actual_tool_cost not recorded: WorkerRun.usage_record_id "
    "references a UsageRecord table no writer in this codebase produces yet -- "
    "disclosed gap, not a fabricated zero."
)


@dataclass(frozen=True)
class TelemetryOutcome:
    """One deterministic telemetry computation, before persistence."""

    actual_verified_outcome: Literal["PASSED", "FAILED"]
    verification_confidence: float
    rework_count: int
    escalated: bool
    human_intervention_required: bool
    recovery_action: str | None
    failure_class: str | None
    elapsed_seconds: float | None
    disclosed_gaps: tuple[str, ...]
