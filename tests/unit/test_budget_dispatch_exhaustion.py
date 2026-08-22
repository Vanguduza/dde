"""Typed budget exhaustion at dispatch (research §6 item 3) -- pure unit
tests plus PostgreSQL-backed proofs of the full budget loop.

Pure part: `engine.workers.budget` value object, encoding/decoding,
resolution rule and admission check.

Production call site under test: `engine.workers.service.
WorkerManagerService.invoke_run` / `resume_run` (the dispatch path)
resolve the ceiling as: caller-supplied `budget` parameter overrides,
else the durable ceiling decoded from the persisted
`execution_plans.token_budget` (`attempt_max_tokens`, recorded by
`ExecutionPlanService.plan(attempt_budget=...)` before hashing), else
unlimited. The check runs inside the idempotency-guarded command body --
after the ledger's replay short-circuit, BEFORE any CapabilityLease or
adapter side effect -- and exceeding the resolved ceiling raises typed
`BudgetExhaustedError` (`BUDGET_EXCEEDED`, Chapter 15.4). On a first-seen
refusal the dispatcher records a durable FAILED TaskAttempt
(`failure_class="BUDGET_EXCEEDED"`) -- exactly the row
`RecoveryService.assert_clear_to_retry` feeds to the recovery matrix,
whose RESOURCE_EXHAUSTION row is pause-for-human (`request_budget`,
`requires_human=True`, no new worker run). The budget is deliberately
NOT part of `_invoke_request_hash` and is evaluated only after replay,
so idempotency wins over budget: a replayed key returns the first call's
stored outcome even under a now-exceeded ceiling. Still honest (also
stated in `engine.workers.budget`'s docstring): Stage 1 has no token
meter -- the check compares declared demand against the ceiling at
admission time; live provider metering remains deferred.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.contracts.context_package import ContextPackage
from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.contracts.workspace import Workspace
from engine.core.errors import BudgetExhaustedError, DdeError
from engine.execution.repository import ExecutionPlanRepository
from engine.execution.service import ExecutionPlanService
from engine.missions.attempts import TaskAttemptRepository
from engine.recovery.dispatch import RecoveryService
from engine.recovery.matrix import canonical_failure_class, decide
from engine.truth.db import open_unit_of_work
from engine.workers.adapter import WorkerAction
from engine.workers.budget import (
    ATTEMPT_MAX_TOKENS_KEY,
    AttemptBudget,
    attempt_budget_from_plan,
    attempt_budget_json,
    check_attempt_budget,
    estimated_token_demand,
    resolve_attempt_budget,
)
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.repository import WorkerRunRepository
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.capability_fixtures import ensure_capabilities_seeded
from tests.support.db import TenantFixture, new_engine
from tests.support.execution_fixtures import build_execution_fixture
from tests.support.worker_fixtures import build_worker_fixture


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
    """The recovery matrix classifies BUDGET_EXCEEDED onto
    RESOURCE_EXHAUSTION (request_budget, requires_human=True, no new
    worker run) -- the pause-for-human outcome research §6 asks for.
    Production wiring: the dispatcher records exactly this failure class
    on a durable FAILED TaskAttempt (PostgreSQL tests below);
    `RecoveryService.assert_clear_to_retry` feeds that row to `decide()`
    on every later dispatch for the task."""
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


def test_encoding_round_trip_and_effort_hint_is_not_a_ceiling() -> None:
    """Only the keys this module owns encode/decode; the planner's plain
    effort-derived `{"max_tokens": ...}` hint must NOT decode into an
    enforced ceiling (plans persisted before budgets were enforceable
    stay unlimited), and malformed values degrade to absent instead of
    raising or silently capping."""
    encoded = attempt_budget_json(AttemptBudget(max_tokens=500))
    assert encoded == {"attempt_max_tokens": 500}
    assert attempt_budget_from_plan(encoded) == AttemptBudget(max_tokens=500)

    both = attempt_budget_json(AttemptBudget(max_tokens=10, max_tool_calls=2))
    assert attempt_budget_from_plan(both) == AttemptBudget(
        max_tokens=10, max_tool_calls=2
    )

    # Effort-derived planner hint alone is not a dispatch ceiling.
    assert attempt_budget_from_plan({"max_tokens": 20_000}) is None

    # Malformed values never become ceilings.
    assert attempt_budget_from_plan({"attempt_max_tokens": "huge"}) is None
    assert attempt_budget_from_plan({"attempt_max_tokens": True}) is None
    assert attempt_budget_from_plan(None) is None
    assert attempt_budget_from_plan({}) is None


def test_resolution_caller_overrides_durable_ceiling() -> None:
    """Dispatch-time rule: caller param wins; durable plan ceiling
    applies when the caller passes none; neither means unlimited."""
    durable = {"attempt_max_tokens": 100}
    override = AttemptBudget(max_tokens=5)
    assert resolve_attempt_budget(override, durable) == override

    from_plan = resolve_attempt_budget(None, durable)
    assert from_plan == AttemptBudget(max_tokens=100)

    assert resolve_attempt_budget(None, {"max_tokens": 20_000}) is None
    assert resolve_attempt_budget(None, None) is None


async def _fresh_manager(
    db_engine: AsyncEngine, workspaces: WorkspaceService
) -> WorkerManagerService:
    """A brand-new service instance over the same database -- durability
    proofs must never depend on cached state of the writing instance."""
    leases = CapabilityLeaseService(db_engine)
    registry = WorkerProfileRegistry()
    await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
    return WorkerManagerService(db_engine, registry, leases=leases)


@dataclass(frozen=True)
class CappedPlanFixture:
    """A real routed verification-class task whose ONE persisted plan
    carries an explicit per-attempt ceiling inside its hashed
    `token_budget`, plus that plan's provisioned workspace."""

    tenant: TenantFixture
    mission: Mission
    task: Task
    context_package: ContextPackage
    plan: ExecutionPlan
    workspace: Workspace


async def build_capped_plan_fixture(
    db_engine: AsyncEngine,
    tmp_path: Path,
    *,
    mission_slug: str,
    budget: AttemptBudget | None,
) -> CappedPlanFixture:
    """The same chain `tests.support.worker_fixtures.build_worker_fixture`
    builds, with the ceiling recorded at plan creation instead of left
    absent."""
    execution_fixture = await build_execution_fixture(
        db_engine, tmp_path, mission_slug=mission_slug, task_class="verification"
    )
    await ensure_capabilities_seeded(
        db_engine,
        tenant_id=execution_fixture.tenant.tenant_id,
        project_id=execution_fixture.tenant.project_id,
    )
    planner = ExecutionPlanService(db_engine)
    plan = await planner.plan(
        task=execution_fixture.task,
        route_decision=execution_fixture.route_decision,
        context_package_id=execution_fixture.context_package.package_id,
        attempt_budget=budget,
    )
    assert plan.worker_profile_id == "profile.deterministic_runner"
    workspace = await planner.provision_workspace(
        plan=plan, task=execution_fixture.task, base_revision="HEAD"
    )
    return CappedPlanFixture(
        tenant=execution_fixture.tenant,
        mission=execution_fixture.mission,
        task=execution_fixture.task,
        context_package=execution_fixture.context_package,
        plan=plan,
        workspace=workspace,
    )


@pytest.mark.asyncio
async def test_persisted_ceiling_survives_a_fresh_service_instance(
    tmp_path: Path,
) -> None:
    """(a) Durability: a ceiling recorded at plan creation is part of the
    hashed plan definition. It round-trips through PostgreSQL unchanged,
    decodes back to the same value, and a brand-new service instance --
    sharing nothing with the writer but the database -- enforces it from
    the persisted row alone, with NO caller-supplied budget passed."""
    root = repo_root()
    db_engine = new_engine()
    capped = None
    try:
        capped = await build_capped_plan_fixture(
            db_engine,
            tmp_path,
            mission_slug="MISSION-BUDGET-DURABLE",
            budget=AttemptBudget(max_tokens=1),
        )
        assert capped.plan.token_budget[ATTEMPT_MAX_TOKENS_KEY] == 1

        async with open_unit_of_work(
            db_engine,
            tenant_id=capped.tenant.tenant_id,
            project_id=capped.tenant.project_id,
        ) as uow:
            reloaded = await ExecutionPlanRepository().get_plan(
                uow.connection, capped.plan.plan_id
            )
            await uow.commit()
        assert reloaded == capped.plan
        assert attempt_budget_from_plan(reloaded.token_budget) == AttemptBudget(
            max_tokens=1
        )

        workspaces = WorkspaceService(db_engine, root=root)
        fresh_manager = await _fresh_manager(db_engine, workspaces)
        action = WorkerAction(command=[sys.executable, "-c", "print('x')"])
        assert estimated_token_demand(action) > 1
        with pytest.raises(BudgetExhaustedError):
            await fresh_manager.invoke_run(
                task=capped.task,
                execution_plan=capped.plan,
                workspace=capped.workspace,
                input_context_hash=capped.context_package.assembly_hash,
                action=action,
                idempotency_key="budget-durable-1",
            )
    finally:
        if capped is not None and capped.workspace.status != "CLEANED_UP":
            await WorkspaceService(db_engine, root=root).cleanup(
                workspace=capped.workspace
            )
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_dispatch_over_persisted_ceiling_refuses_and_pauses_for_human(
    tmp_path: Path,
) -> None:
    """(b) Consumption: dispatching over the persisted ceiling raises
    typed BUDGET_EXHAUSTED and records the refusal as the recovery
    machinery's own pause-for-human input: a durable FAILED TaskAttempt
    with failure_class="BUDGET_EXCEEDED" and no WorkerRun (pre-mutation).
    `RecoveryService.assert_clear_to_retry` -- the real production
    consumer -- then refuses any further dispatch for the task with the
    matrix's RESOURCE_EXHAUSTION decision."""
    root = repo_root()
    db_engine = new_engine()
    capped = None
    try:
        capped = await build_capped_plan_fixture(
            db_engine,
            tmp_path,
            mission_slug="MISSION-BUDGET-REFUSAL",
            budget=AttemptBudget(max_tokens=1),
        )
        workspaces = WorkspaceService(db_engine, root=root)
        manager = await _fresh_manager(db_engine, workspaces)
        action = WorkerAction(command=[sys.executable, "-c", "print('x')"])

        with pytest.raises(BudgetExhaustedError):
            await manager.invoke_run(
                task=capped.task,
                execution_plan=capped.plan,
                workspace=capped.workspace,
                input_context_hash=capped.context_package.assembly_hash,
                action=action,
                idempotency_key="budget-refusal-1",
            )

        async with open_unit_of_work(
            db_engine,
            tenant_id=capped.tenant.tenant_id,
            project_id=capped.tenant.project_id,
        ) as uow:
            attempts = await TaskAttemptRepository().list_for_task(
                uow.connection, capped.task.task_id
            )
            await uow.commit()
        refused = [row for row in attempts if row.failure_class == "BUDGET_EXCEEDED"]
        assert len(refused) == 1
        assert refused[0] == attempts[-1]
        assert refused[0].status == "FAILED"

        async with open_unit_of_work(
            db_engine,
            tenant_id=capped.tenant.tenant_id,
            project_id=capped.tenant.project_id,
        ) as uow:
            runs = await WorkerRunRepository().list_for_attempt(
                uow.connection, refused[0].attempt_id
            )
            await uow.commit()
        assert runs == []  # pre-mutation refusal: nothing ever ran

        # The production consumer: the recovery dispatcher reads exactly
        # this FAILED attempt and the matrix pauses for human.
        recovery = RecoveryService(db_engine)
        with pytest.raises(DdeError) as paused:
            await recovery.assert_clear_to_retry(
                tenant_id=capped.tenant.tenant_id,
                project_id=capped.tenant.project_id,
                task_id=capped.task.task_id,
                mission_id=capped.mission.mission_id,
            )
        assert paused.value.error_code == "BUDGET_EXCEEDED"
        assert paused.value.retryable is False
        assert paused.value.details is not None
        assert paused.value.details["failure_class"] == "RESOURCE_EXHAUSTION"
        assert paused.value.details["action"] == "request_budget"

        # Same pause, end-to-end through invoke_run itself: a fresh
        # command whose demand FITS the persisted ceiling is now refused
        # by the recovery matrix before its budget check could pass --
        # RESOURCE_EXHAUSTION never blind-retries.
        fitting_action = WorkerAction(
            command=[sys.executable, "-c", "print('t')"],
        )
        with pytest.raises(DdeError) as repaused:
            await manager.invoke_run(
                task=capped.task,
                execution_plan=capped.plan,
                workspace=capped.workspace,
                input_context_hash=capped.context_package.assembly_hash,
                action=fitting_action,
                idempotency_key="budget-refusal-2",
                budget=AttemptBudget(max_tokens=estimated_token_demand(fitting_action)),
            )
        assert repaused.value.error_code == "BUDGET_EXCEEDED"
        assert repaused.value.details is not None
        assert repaused.value.details["action"] == "request_budget"
    finally:
        if capped is not None and capped.workspace.status != "CLEANED_UP":
            await WorkspaceService(db_engine, root=root).cleanup(
                workspace=capped.workspace
            )
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_replayed_key_with_exhausted_budget_replays_original_outcome(
    tmp_path: Path,
) -> None:
    """(c) Idempotency wins over budget: the first command COMPLETED and
    stored its result in the command ledger; replaying the same key
    under a maximally tight caller-supplied ceiling returns that stored
    outcome without re-running anything -- the budget check sits after
    the ledger's replay short-circuit by design (and the budget is not
    part of `_invoke_request_hash`)."""
    root = repo_root()
    db_engine = new_engine()
    fixture = None
    try:
        fixture = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-BUDGET-REPLAY"
        )
        workspaces = WorkspaceService(db_engine, root=root)
        manager = await _fresh_manager(db_engine, workspaces)
        action = WorkerAction(
            command=[sys.executable, "-c", "print('budget-replay-proof')"]
        )

        first = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=action,
            idempotency_key="budget-replay-1",
        )
        assert first.status == "COMPLETED"

        replayed = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=action,
            idempotency_key="budget-replay-1",
            budget=AttemptBudget(max_tokens=0),
        )
        assert replayed.run_id == first.run_id
        assert replayed.status == "COMPLETED"
    finally:
        if fixture is not None and fixture.workspace.status != "CLEANED_UP":
            await WorkspaceService(db_engine, root=root).cleanup(
                workspace=fixture.workspace
            )
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_caller_override_still_works(tmp_path: Path) -> None:
    """(d) Backwards compatibility: the caller-supplied parameter remains
    an override in both directions. On an uncapped plan a tight explicit
    ceiling refuses; on a plan persisting a tiny durable ceiling a
    generous explicit ceiling admits and the run completes. Two
    independent tasks, because once recorded, a refusal legitimately
    pauses further dispatch for THAT task."""
    root = repo_root()
    db_engine = new_engine()
    uncapped = None
    capped = None
    try:
        # Tight caller override on an uncapped plan: refuses.
        uncapped = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-BUDGET-OVERRIDE-A"
        )
        workspaces_a = WorkspaceService(db_engine, root=root)
        manager_a = await _fresh_manager(db_engine, workspaces_a)
        action_a = WorkerAction(
            command=[sys.executable, "-c", "print('override-refused')"],
            write_files={"pad.txt": b"x" * 64},
        )
        assert estimated_token_demand(action_a) > 8
        with pytest.raises(BudgetExhaustedError) as excinfo:
            await manager_a.invoke_run(
                task=uncapped.task,
                execution_plan=uncapped.execution_plan,
                workspace=uncapped.workspace,
                input_context_hash=uncapped.context_package.assembly_hash,
                action=action_a,
                idempotency_key="override-tight-1",
                budget=AttemptBudget(max_tokens=8),
            )
        assert excinfo.value.error_code == "BUDGET_EXCEEDED"
        assert excinfo.value.details is not None
        assert excinfo.value.details["max_tokens"] == 8

        # Generous caller override beats a persisted tiny ceiling.
        capped = await build_capped_plan_fixture(
            db_engine,
            tmp_path,
            mission_slug="MISSION-BUDGET-OVERRIDE-B",
            budget=AttemptBudget(max_tokens=1),
        )
        workspaces_b = WorkspaceService(db_engine, root=root)
        manager_b = await _fresh_manager(db_engine, workspaces_b)
        action_b = WorkerAction(
            command=[sys.executable, "-c", "print('override-admitted')"]
        )
        run = await manager_b.invoke_run(
            task=capped.task,
            execution_plan=capped.plan,
            workspace=capped.workspace,
            input_context_hash=capped.context_package.assembly_hash,
            action=action_b,
            idempotency_key="override-generous-1",
            budget=AttemptBudget(max_tokens=estimated_token_demand(action_b)),
        )
        assert run.status == "COMPLETED"
    finally:
        for built in (uncapped, capped):
            if built is not None and built.workspace.status != "CLEANED_UP":
                await WorkspaceService(db_engine, root=root).cleanup(
                    workspace=built.workspace
                )
        await db_engine.dispose()
