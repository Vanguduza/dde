"""Per-attempt dispatch budgets (Chapter 8.4) — admission-checked at the
dispatch call sites and persisted on the ExecutionPlan.

**What is wired.**
- `AttemptBudget` remains an optional parameter on
  `WorkerManagerService.invoke_run`/`resume_run`. When supplied it
  *overrides* whatever the durable ExecutionPlan carries; it never
  silently widens a persisted ceiling.
- **Persistence (zero-schema-change).** The durable home for a ceiling is
  `execution_plans.token_budget` — the Chapter 7.1 budget JSONB the
  planner already hashes and persists (it has always carried
  `{"max_tokens": <effort-derived int>}` for every plan).
  `ExecutionPlanService.plan(attempt_budget=...)` merges the caller's
  ceiling into that object *before* `plan_hash` is computed, so the
  ceiling is part of the immutable plan definition and survives any
  process restart. No new column, no migration, no second source of
  truth: the field existed; only its population did not.
- **Resolution.** `resolve_attempt_budget` implements the dispatch-time
  rule: caller parameter wins, else the ceiling decoded from the
  persisted plan, else unlimited (`None`).
- **Consumption.** On refusal, `WorkerManagerService` records
  `failure_class="BUDGET_EXCEEDED"` on a durable `TaskAttempt` via the
  existing `TaskAttemptService.fail()` — the exact row
  `RecoveryService.assert_clear_to_retry` already reads and feeds to
  `engine.recovery.matrix.decide()`, where the `BUDGET_EXCEEDED` alias
  lands on the RESOURCE_EXHAUSTION row (`action="request_budget"`,
  `requires_human=True`, `allow_new_worker_run=False`): the
  pause-for-human outcome, reached through machinery that already
  existed. No new event type, no new state, no new subsystem.

**What remains honest / unwired.**
- This is an admission check, not a metered decrement. There are no
  token counters anywhere in Stage 1 (`ScriptedWorkerAdapter.
  collect_usage` reports zero model usage), so the check compares the
  attempt's declared demand (`estimated_token_demand`: its literal
  instruction payload, plus one tool invocation per dispatch) against
  the ceiling before anything runs. Live provider metering remains
  deferred.
- **Idempotency: the budget is deliberately NOT part of
  `_invoke_request_hash`.** The request hash pins the *identity* of the
  logical command; `CommandLedger.begin` outright refuses a key that
  reappears with a different hash. Folding the ceiling into the hash
  would (a) turn "same command, different admission policy" into a hard
  `VERSION_CONFLICT` instead of a policy evaluation, and (b) fork the
  identity of already-issued commands the moment a ceiling became
  persisted default rather than a caller parameter. Instead the budget
  is execution-time admission policy evaluated *after* the ledger
  short-circuit — so idempotency wins over budget: a replayed command
  whose budget has since been exhausted still replays the first call's
  stored outcome, because the replay path returns before the check ever
  runs. (A first-seen command under an exhausted ceiling is a *new*
  command identity and is refused.)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from engine.core.errors import BudgetExhaustedError
from engine.workers.adapter import WorkerAction

#: The failure class recorded on a durable TaskAttempt when the ceiling
#: refuses a dispatch. It is the recovery matrix's own alias token
#: (`FAILURE_CLASS_ALIASES["BUDGET_EXCEEDED"] -> RESOURCE_EXHAUSTION`),
#: not a new taxonomy entry.
BUDGET_EXCEEDED_FAILURE_CLASS = "BUDGET_EXCEEDED"


@dataclass(frozen=True)
class AttemptBudget:
    """Ceiling for ONE dispatch attempt. Both fields optional
    independently: a caller may cap tokens, tool invocations, both, or
    neither."""

    max_tokens: int | None = None
    max_tool_calls: int | None = None

    def __post_init__(self) -> None:
        if self.max_tokens is not None and self.max_tokens < 0:
            raise ValueError("max_tokens must be >= 0")
        if self.max_tool_calls is not None and self.max_tool_calls < 0:
            raise ValueError("max_tool_calls must be >= 0")

    @property
    def unlimited(self) -> bool:
        return self.max_tokens is None and self.max_tool_calls is None


#: Keys this module owns inside `execution_plans.token_budget`. The JSONB
#: already carried a planner-written cost hint (`{"max_tokens": <int>}`,
#: derived from `Task.estimated_effort`) long before budgets were
#: enforceable, so an enforced per-attempt ceiling gets its own,
#: unambiguous keys instead of overloading that hint -- plans created
#: without one keep their exact prior behaviour.
ATTEMPT_MAX_TOKENS_KEY = "attempt_max_tokens"
ATTEMPT_MAX_TOOL_CALLS_KEY = "attempt_max_tool_calls"


def attempt_budget_json(budget: AttemptBudget | None) -> dict[str, int]:
    """Encode a ceiling into the keys this module owns inside
    `execution_plans.token_budget`. Empty dict encodes "no explicit
    per-attempt ceiling"; the caller (`ExecutionPlanService.plan`) merges
    these keys over the effort-derived hint before hashing."""

    encoded: dict[str, int] = {}
    if budget is None:
        return encoded
    if budget.max_tokens is not None:
        encoded[ATTEMPT_MAX_TOKENS_KEY] = budget.max_tokens
    if budget.max_tool_calls is not None:
        encoded[ATTEMPT_MAX_TOOL_CALLS_KEY] = budget.max_tool_calls
    return encoded


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def attempt_budget_from_plan(
    token_budget: Mapping[str, object] | None,
) -> AttemptBudget | None:
    """Decode the durable ceiling back out of a persisted
    `token_budget`. Reads only the keys this module owns, so the plain
    effort-derived `{"max_tokens": ...}` shape stays what it always was
    -- a planner cost hint, not a per-attempt dispatch ceiling -- and
    decodes to `None`. Malformed values degrade to absent rather than
    raising: nothing here may turn a corrupt field into either an
    unexpected refusal or a silently disabled check."""

    if not token_budget:
        return None
    max_tokens = _int_or_none(token_budget.get(ATTEMPT_MAX_TOKENS_KEY))
    max_tool_calls = _int_or_none(token_budget.get(ATTEMPT_MAX_TOOL_CALLS_KEY))
    if max_tokens is None and max_tool_calls is None:
        return None
    return AttemptBudget(max_tokens=max_tokens, max_tool_calls=max_tool_calls)


def resolve_attempt_budget(
    budget: AttemptBudget | None,
    token_budget: Mapping[str, object] | None,
) -> AttemptBudget | None:
    """Dispatch-time resolution rule: the caller-supplied parameter is an
    override and wins; otherwise the ceiling persisted on the
    ExecutionPlan applies; otherwise unlimited. A caller can tighten a
    durable ceiling but never widen one by omission."""

    if budget is not None:
        return budget
    return attempt_budget_from_plan(token_budget)


def _over(
    *,
    ceiling: int | None,
    demanded: int,
    kind: str,
) -> str | None:
    if ceiling is not None and demanded > ceiling:
        return kind
    return None


def estimated_token_demand(action: WorkerAction) -> int:
    """Stage 1's honest demand model: there is no token meter anywhere in
    this codebase (`ScriptedWorkerAdapter.collect_usage` reports zero model
    usage), so the only real, measurable input an attempt carries is its
    literal instruction payload. This counts it -- a ceiling below the
    payload size refuses dispatch before anything runs; a ceiling above it
    passes. It is NOT a model-token prediction and must not be read as one."""
    payload = b"".join(
        [part.encode("utf-8") for part in action.command]
        + list(action.write_files.values())
    )
    return len(payload)


def check_attempt_budget(
    budget: AttemptBudget | None,
    *,
    estimated_tokens: int,
    estimated_tool_calls: int,
) -> None:
    """Admission check at the dispatch site: raise typed
    `BudgetExhaustedError` when this attempt's declared demand does not fit
    under the resolved ceiling. `budget=None` returns immediately --
    the unlimited case keeps existing call sites byte-identical."""
    if budget is None:
        return
    exhausted = _over(
        ceiling=budget.max_tokens,
        demanded=estimated_tokens,
        kind="tokens",
    ) or _over(
        ceiling=budget.max_tool_calls,
        demanded=estimated_tool_calls,
        kind="tool_calls",
    )
    if exhausted is None:
        return
    details: dict[str, object] = {
        "budget_kind": exhausted,
        "estimated_tokens": estimated_tokens,
        "estimated_tool_calls": estimated_tool_calls,
    }
    if budget.max_tokens is not None:
        details["max_tokens"] = budget.max_tokens
    if budget.max_tool_calls is not None:
        details["max_tool_calls"] = budget.max_tool_calls
    raise BudgetExhaustedError(
        f"attempt exceeds its {exhausted} budget ceiling -- refusing to dispatch",
        details=details,
    )
