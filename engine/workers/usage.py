"""Live per-run usage metering helpers (Chapter 8.2/8.4 budgets, runtime half).

**Where remaining budget lives -- derived, never stored twice.** The
durable ceiling already persists on `execution_plans.token_budget` (the
keys `engine.workers.budget` owns, recorded before hashing). Consumption
persists as ordinary `worker_events` rows (`event_type=
"WorkerRunUsageReported"`) whose payload carries the report's token
totals. Remaining budget is therefore always DERIVED: ceiling minus the
sum of report payloads for the run. There is no balance column, no new
table, no migration, and no second source of truth -- the reports live
exactly where every other per-run fact already lives
(`worker_events`, owned by `engine.workers`), satisfying the mission
brief's preference for "budget minus sum-of-reports stored wherever
WorkerRun rows already live".

**Honest ingestion status (disclosed deferral, not a fake call site).**
No production call site forwards usage today. Every certified adapter
reports zero model usage: `ScriptedWorkerAdapter.collect_usage` and
`ClaudeCodeWorkerAdapter.collect_usage` return honestly-zero
`UsageRecord(duration_ms=..., cost_usd=0.0)` values (EDR-0001 Research
Finding 3: a subscription seat gives DDE no token visibility), and
`CursorWorkerAdapter.start()` fails closed before any model runs --
there is nothing real to forward, and fabricating a call site is the
exact dishonesty this codebase forbids (cf.
`docs/planning/gap-closure-record.md` item 1, EDR-0005). The public
writer `WorkerManagerService.record_run_usage` ships tested and ready;
the moment any adapter yields real figures, forwarding them through it
is the entire integration. Even the shadow-promotion elapsed-seconds
precedent does not help here: elapsed time is already captured on
`RunHandle` payloads by `_drive_lifecycle`, so adapters hold no
additional signal beyond zeros today.

**Zero-crossing reuses commit 0464933's pause machinery.** When a report
pushes derived remaining to zero-or-below, the writer records the SAME
durable outcome the dispatch-time admission check does: a FAILED
TaskAttempt with `failure_class="BUDGET_EXCEEDED"` via the existing
`TaskAttemptService.fail()`, which `RecoveryService.assert_clear_to_retry`
feeds to `engine.recovery.matrix.decide()` -- RESOURCE_EXHAUSTION,
`action="request_budget"`, `requires_human=True`, no new worker run.
No parallel mechanism is invented.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from engine.contracts.worker_event import WorkerEvent
from engine.workers.budget import ATTEMPT_MAX_TOKENS_KEY

#: Per-run worker-event / generic event-store type for a forwarded usage
#: report -- Chapter 8.3's PascalCase convention, matching
#: `WorkerRunCreated`/`WorkerRunCompleted`.
USAGE_REPORTED_EVENT_TYPE = "WorkerRunUsageReported"

#: `token_budget` key holding the planner's non-enforced effort-derived
#: hint. When a plan carries no explicit per-attempt ceiling, metering
#: degrades to this declared budget rather than to unlimited, so a
#: reported overrun is still observable against something the planner
#: actually wrote.
PLANNER_HINT_MAX_TOKENS_KEY = "max_tokens"


@dataclass(frozen=True)
class RecordedUsage:
    """Outcome of one accepted `record_run_usage` command."""

    event_sequence: int
    consumed_tokens: int
    ceiling_tokens: int | None
    remaining_tokens: int | None
    budget_exceeded: bool


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def ceiling_tokens_from_plan(
    token_budget: Mapping[str, object] | None,
) -> int | None:
    """The enforced ceiling a run's reports decrement against:
    `engine.workers.budget`'s own `attempt_max_tokens` key when present,
    else the planner's effort-derived `max_tokens` hint, else `None`
    (= unlimited -- reports are recorded and observable but never
    cross anything)."""

    if not token_budget:
        return None
    explicit = _int_or_none(token_budget.get(ATTEMPT_MAX_TOKENS_KEY))
    if explicit is not None:
        return explicit
    return _int_or_none(token_budget.get(PLANNER_HINT_MAX_TOKENS_KEY))


def remaining_tokens(*, ceiling: int | None, consumed: int) -> int | None:
    """Derived remaining budget: `ceiling - consumed`; `None` when the
    run is unlimited."""
    if ceiling is None:
        return None
    return ceiling - consumed


def total_tokens_of(
    *,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int | None,
) -> int:
    """A caller-supplied total wins; otherwise input+output."""
    if total_tokens is not None:
        return total_tokens
    return input_tokens + output_tokens


def consumed_tokens_from_worker_events(events: Sequence[WorkerEvent]) -> int:
    """Sum the token totals of this run's usage-report events. Payload
    values that are not plain ints degrade to zero rather than raising:
    a malformed historical payload must never break metering for the
    run's remaining reports."""

    total = 0
    for event in events:
        if event.event_type != USAGE_REPORTED_EVENT_TYPE:
            continue
        value = _int_or_none(event.payload.get("total_tokens"))
        if value is not None and value > 0:
            total += value
    return total
