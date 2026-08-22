"""Typed budget exhaustion at dispatch (research §6 item 3) -- pure unit
tests, no PostgreSQL.

Production call site under test: `engine.workers.service.
WorkerManagerService.invoke_run` / `resume_run` (the dispatch path) call
`check_attempt_budget` inside the idempotency-guarded command body --
BEFORE any TaskAttempt row, CapabilityLease, or adapter side effect exists
for the attempt. Exceeding a caller-supplied ceiling raises typed
`BudgetExhaustedError` (`BUDGET_EXHAUSTED`, Chapter 15.4) and performs no
durable mutation. Honest scope, also stated in `engine.workers.budget`'s
docstring: the budget is caller-supplied only -- not persisted, not part of
the request hash; default None = unlimited = behaviour unchanged. Nothing
consumes the refusal downstream yet: landing it as the recovery matrix's
RESOURCE_EXHAUSTION pause-for-human row needs a durable run/attempt to
attach to and is deferred.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from engine.core.errors import BudgetExhaustedError, DdeError
from engine.recovery.matrix import canonical_failure_class, decide
from engine.workers.adapter import WorkerAction
from engine.workers.budget import (
    AttemptBudget,
    check_attempt_budget,
    estimated_token_demand,
)


def _action() -> WorkerAction:
    return WorkerAction(
        command=("python", "-c", "print('x')"),
        write_files={"src/feature.py": b"print('hello world')\n"},
    )


def test_default_none_budget_is_unlimited_and_never_raises() -> None:
    """Default behaviour contract: `budget=None` returns immediately, so
    every existing caller is byte-identical to a build without the
    parameter."""
    check_attempt_budget(
        None,
        estimated_tokens=10**12,
        estimated_tool_calls=10**9,
    )


def test_demand_under_ceiling_passes() -> None:
    demand = estimated_token_demand(_action())
    check_attempt_budget(
        AttemptBudget(max_tokens=demand + 1),
        estimated_tokens=demand,
        estimated_tool_calls=1,
    )


def test_exact_ceiling_is_not_exhaustion() -> None:
    """The ceiling is inclusive: an attempt demanding exactly the cap is
    admitted; only exceeding it refuses."""
    check_attempt_budget(
        AttemptBudget(max_tokens=100),
        estimated_tokens=100,
        estimated_tool_calls=1,
    )


def test_exceeded_token_budget_raises_typed_error_with_details() -> None:
    with pytest.raises(BudgetExhaustedError) as excinfo:
        check_attempt_budget(
            AttemptBudget(max_tokens=10),
            estimated_tokens=25,
            estimated_tool_calls=1,
        )
    err = excinfo.value
    assert isinstance(err, DdeError)
    assert err.error_code == "BUDGET_EXCEEDED"
    assert err.retryable is False
    assert err.details is not None
    assert err.details["budget_kind"] == "tokens"
    assert err.details["max_tokens"] == 10
    assert err.details["estimated_tokens"] == 25


def test_exceeded_tool_call_budget_names_the_kind() -> None:
    with pytest.raises(BudgetExhaustedError) as excinfo:
        check_attempt_budget(
            AttemptBudget(max_tool_calls=0),
            estimated_tokens=1,
            estimated_tool_calls=1,
        )
    assert excinfo.value.error_code == "BUDGET_EXCEEDED"
    assert excinfo.value.details is not None
    assert excinfo.value.details["budget_kind"] == "tool_calls"


def test_error_maps_onto_chapter_15_contract() -> None:
    """The typed error must survive the boundary mapping to the gateway
    Error contract (`DdeError.to_contract`) with its code intact."""
    try:
        check_attempt_budget(
            AttemptBudget(max_tokens=0),
            estimated_tokens=1,
            estimated_tool_calls=0,
        )
    except BudgetExhaustedError as err:
        contract = err.to_contract()
        assert contract.error_code == "BUDGET_EXCEEDED"
        assert contract.retryable is False


def test_negative_budgets_are_rejected_at_construction() -> None:
    with pytest.raises(ValueError):
        AttemptBudget(max_tokens=-1)
    with pytest.raises(ValueError):
        AttemptBudget(max_tool_calls=-5)


def test_estimated_token_demand_counts_the_real_payload() -> None:
    """Stage 1 has no token meter; the honest demand model is the literal
    instruction payload (argv + written file bytes), counted in UTF-8
    bytes."""
    action = WorkerAction(command=("python", "--version"))
    assert estimated_token_demand(action) == len(b"python--version")
    payload_action = WorkerAction(
        command=("python", "-c", "x"),
        write_files={"a.py": b"12345"},
    )
    assert estimated_token_demand(payload_action) == len(b"python-cx") + 5


def test_budget_refusal_maps_to_resource_exhaustion_row() -> None:
    """The recovery matrix already classifies BUDGET_EXCEEDED-shaped codes
    onto RESOURCE_EXHAUSTION (request_budget, requires_human=True, no new
    worker run) -- i.e., the pause-for-human outcome research §6 asks for.
    This pins that the typed code lands on exactly that row when a future
    dispatcher records it; wiring that consumer remains deferred."""
    assert canonical_failure_class("BUDGET_EXCEEDED") == "RESOURCE_EXHAUSTION"
    decision = decide("BUDGET_EXCEEDED", occurrence_count=1)
    assert decision.action == "request_budget"
    assert decision.requires_human is True
    assert decision.allow_new_worker_run is False


def test_unlimited_budget_object_admits_anything() -> None:
    budget = AttemptBudget()
    assert budget.unlimited is True
    check_attempt_budget(
        budget,
        estimated_tokens=10**12,
        estimated_tool_calls=10**9,
    )


def test_run_id_style_details_are_not_required_for_typing() -> None:
    """A caller can catch the typed error without inspecting details --
    the subclass exists precisely so dispatch sites distinguish budget
    refusals from other POLICY_DENIED-shaped errors without string
    matching."""
    caught: list[type[Exception]] = []
    try:
        check_attempt_budget(
            AttemptBudget(max_tokens=0),
            estimated_tokens=1,
            estimated_tool_calls=0,
        )
    except BudgetExhaustedError:
        caught.append(BudgetExhaustedError)
    except DdeError:  # pragma: no cover - proves subclassing order
        caught.append(DdeError)
    assert caught == [BudgetExhaustedError]
    assert uuid4()  # keep uuid import meaningful for future assertions
