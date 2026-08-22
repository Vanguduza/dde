"""Chapter 6.5 real-telemetry computation -- pure, over already-computed
production signals.

Chapter 6.5: "Even under deterministic routing, DDE records for every
decision: candidate set with elimination gates, predictions, selection
propensity, actual verified outcome, verification confidence, rework
count, escalation, human intervention, actual token/tool cost, elapsed
time, failure class, recovery path, context policy version, capability
set, and the attribution from Sec5.11. This is cheap, must never be
skipped, and is the only thing that makes later learning possible without
an architectural migration."

The first three fields (candidate set, predictions, selection propensity)
are already durable on `RouteDecision` at routing time -- this module
never re-derives or duplicates them, only the outcome-side fields a
`RouteDecision` cannot know about itself:

- **actual verified outcome / verification confidence** -- the real
  `VerificationRun.status`/`.confidence` `engine.verification.runner`
  already computed.
- **rework count** -- the real count of prior `FAILED` `VerificationRun`
  rows for this task `engine.verification.runner`'s own `FAILED` branch
  already computes for `engine.recovery.matrix.decide`.
- **escalation / human intervention / recovery path** -- the real
  `engine.recovery.matrix.RecoveryDecision` the runner's `FAILED` branch
  already computes: `action` is the recovery path; `requires_human` is
  the genuine Chapter 12.3 human-intervention signal (not a guess);
  `action == "escalate"` is the genuine escalation signal.
- **failure class** -- the real, canonical failure class `decide()` was
  called with (`VERIFICATION_FAILURE` for every call site this Stage 1
  slice wires, since `engine.verification.runner` is currently the only
  production caller of `engine.telemetry`).
- **elapsed time** -- the real `VerificationRun.started_at`/`.ended_at`
  wall-clock span.

**Not implemented for real** (disclosed on every row via `disclosed_gaps`,
never silently defaulted): **actual token/tool cost**.
`WorkerRun.usage_record_id` references a `UsageRecord` concept no writer
in this codebase produces yet.

**context policy version / capability set** are not computed here --
`engine.telemetry.service` reads the real, already-persisted
`ContextPackage.package_id` and `ExecutionPlan.capability_requirements`
directly, since no separate "context policy version" concept exists yet
(Chapter 5.13/promotion-gate territory) and `context_package_id` is the
real durable pointer standing in for it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from engine.recovery.matrix import RecoveryDecision
from engine.telemetry.model import ACTUAL_COST_GAP_DISCLOSED, TelemetryOutcome


def compute_outcome(
    *,
    status: Literal["PASSED", "FAILED"],
    confidence: float,
    rework_count: int,
    recovery_decision: RecoveryDecision | None,
    started_at: datetime,
    ended_at: datetime | None,
) -> TelemetryOutcome:
    """`recovery_decision` is `None` exactly when `status == "PASSED"` --
    `engine.recovery.matrix.decide` is a recovery-path lookup and a
    passing run has nothing to recover from. A `FAILED` status with no
    `recovery_decision` is a caller error, not a value this module can
    silently paper over."""
    if status == "FAILED" and recovery_decision is None:
        raise ValueError("a FAILED outcome requires its real RecoveryDecision")
    if status == "PASSED" and recovery_decision is not None:
        raise ValueError("a PASSED outcome must not carry a RecoveryDecision")

    elapsed_seconds = (
        (ended_at - started_at).total_seconds() if ended_at is not None else None
    )

    if recovery_decision is None:
        return TelemetryOutcome(
            actual_verified_outcome=status,
            verification_confidence=confidence,
            rework_count=rework_count,
            escalated=False,
            human_intervention_required=False,
            recovery_action=None,
            failure_class=None,
            elapsed_seconds=elapsed_seconds,
            disclosed_gaps=(ACTUAL_COST_GAP_DISCLOSED,),
        )

    return TelemetryOutcome(
        actual_verified_outcome=status,
        verification_confidence=confidence,
        rework_count=rework_count,
        escalated=recovery_decision.action == "escalate",
        human_intervention_required=recovery_decision.requires_human,
        recovery_action=recovery_decision.action,
        failure_class=recovery_decision.failure_class,
        elapsed_seconds=elapsed_seconds,
        disclosed_gaps=(ACTUAL_COST_GAP_DISCLOSED,),
    )
