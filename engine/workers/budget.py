"""Caller-supplied dispatch budgets (Chapter 8.4's per-attempt ceiling).

**What is wired.** `AttemptBudget` is an optional, caller-supplied value
object on `WorkerManagerService.invoke_run`/`resume_run` (the production
dispatch call sites). `check()` runs inside the idempotency-guarded command
body -- before any `TaskAttempt` row, any `CapabilityLease`, and any
adapter side effect is created for this attempt.

**What remains caller-supplied / unwired (stated plainly).**
- The budget is a Python parameter only: it is not persisted anywhere, not
  part of `ExecutionPlan.token_budget` resolution, not part of
  `_invoke_request_hash` (a replay of the same idempotency key replays the
  first call's outcome regardless of the second caller's budget), and not
  enforced against any provider-side meter. There are no token counters to
  decrement in Stage 1 (`ScriptedWorkerAdapter.collect_usage` honestly
  reports zero model usage), so the check compares the attempt's declared
  demand (`estimated_token_demand`: its literal instruction payload) against
  the ceiling at admission time -- an admission check, not a metered
  decrement.
- Nothing consumes a refusal downstream yet: exhaustion raises typed
  `BudgetExhaustedError` before any mutation; landing it as the recovery
  matrix's RESOURCE_EXHAUSTION row (pause-for-human,
  `action="request_budget"`) on a durable run/attempt is deferred -- there
  is no run row yet at the point the check fires, and inventing one would
  violate the no-second-source-of-truth rule.
- Default `None` = unlimited = behaviour byte-identical to a build without
  this parameter.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.core.errors import BudgetExhaustedError
from engine.workers.adapter import WorkerAction


@dataclass(frozen=True)
class AttemptBudget:
    """Ceiling for ONE dispatch attempt, supplied by whoever calls
    `invoke_run`. Both fields optional independently: a caller may cap
    tokens, tool invocations, both, or neither."""

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
    under the supplied ceiling. `budget=None` returns immediately -- the
    unlimited default keeps existing call sites byte-identical."""
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
        f"attempt exceeds its caller-supplied {exhausted} budget -- "
        "refusing to dispatch",
        details=details,
    )
