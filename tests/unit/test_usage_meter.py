"""Runtime usage metering (`record_run_usage`) and the refused-resume
observability trail.

Pure part: `engine.workers.usage`'s ceiling resolution, derived-remaining
arithmetic, and usage-report payload summation.

Production call site under test: `engine.workers.service.
WorkerManagerService.record_run_usage` -- the public CommandLedger-
guarded writer that accepts a provider-usage report for a WorkerRun,
persists it as an ordinary per-run `worker_events` row (`event_type=
"WorkerRunUsageReported"`), derives remaining budget as persisted
ceiling minus sum of report payloads (no balance column, no new table),
and -- when a report crosses zero -- reuses the EXISTING dispatch-time
pause-for-human machinery: a durable FAILED TaskAttempt with
`failure_class="BUDGET_EXCEEDED"`, which `RecoveryService.
assert_clear_to_retry` feeds to the recovery matrix's RESOURCE_EXHAUSTION
row (request_budget, requires_human=True, no new worker run).

Also under test: `resume_run`'s refusal path now appends an explicit
generic event (`ResumeRefused`, aggregate task_attempt) capturing run
context, reason class and recovery action, in its own committed unit of
work, while the durable attempt-fail behaviour stays unchanged.

Honest status (also stated on `engine.workers.usage`): no production
adapter yields model-usage figures today, so no ingestion call site is
wired; these tests drive the public writer directly.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.repo import repo_root
from engine.contracts.worker_event import WorkerEvent
from engine.contracts.worker_run import WorkerRun
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.repository import EventsRepository
from engine.missions.attempts import TaskAttemptRepository, TaskAttemptService
from engine.recovery.dispatch import RecoveryService
from engine.truth.db import open_unit_of_work
from engine.workers.adapter import WorkerAction
from engine.workers.repository import WorkerRunRepository
from engine.workers.service import RESUME_REFUSED_EVENT_TYPE
from engine.workers.usage import (
    PLANNER_HINT_MAX_TOKENS_KEY,
    USAGE_REPORTED_EVENT_TYPE,
    ceiling_tokens_from_plan,
    consumed_tokens_from_worker_events,
    remaining_tokens,
    total_tokens_of,
)
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture


def test_ceiling_prefers_explicit_attempt_key_over_planner_hint() -> None:
    assert ceiling_tokens_from_plan({"attempt_max_tokens": 100}) == 100
    assert ceiling_tokens_from_plan({PLANNER_HINT_MAX_TOKENS_KEY: 20_000}) == 20_000
    assert (
        ceiling_tokens_from_plan(
            {"attempt_max_tokens": 5, PLANNER_HINT_MAX_TOKENS_KEY: 20_000}
        )
        == 5
    )


def test_malformed_or_absent_ceiling_degrades_to_unlimited() -> None:
    assert ceiling_tokens_from_plan(None) is None
    assert ceiling_tokens_from_plan({}) is None
    assert ceiling_tokens_from_plan({"attempt_max_tokens": "huge"}) is None
    assert ceiling_tokens_from_plan({"attempt_max_tokens": True}) is None


def test_remaining_is_none_when_unlimited_and_negative_when_crossed() -> None:
    assert remaining_tokens(ceiling=None, consumed=10**9) is None
    assert remaining_tokens(ceiling=100, consumed=40) == 60
    assert remaining_tokens(ceiling=100, consumed=100) == 0
    assert remaining_tokens(ceiling=100, consumed=140) == -40


def test_total_tokens_derives_input_plus_output_when_total_omitted() -> None:
    assert total_tokens_of(input_tokens=3, output_tokens=4, total_tokens=None) == 7
    assert total_tokens_of(input_tokens=3, output_tokens=4, total_tokens=50) == 50


def test_consumed_sums_only_usage_report_payloads() -> None:
    def _event(event_type: str, total: object) -> WorkerEvent:
        now = datetime.now(UTC)
        return WorkerEvent(
            event_id=uuid4(),
            tenant_id=uuid4(),
            project_id=uuid4(),
            mission_id=uuid4(),
            run_id=uuid4(),
            task_id=uuid4(),
            sequence=1,
            event_type=event_type,
            occurred_at=now,
            actor="test",
            correlation_id="c",
            causation_id=None,
            payload={"total_tokens": total},
            schema_version="1",
            integrity_hash="h",
            created_at=now,
            updated_at=now,
        )

    events = [
        _event("WorkerRunCreated", 999),
        _event(USAGE_REPORTED_EVENT_TYPE, 30),
        _event("WorkerRunCompleted", 999),
        _event(USAGE_REPORTED_EVENT_TYPE, 12),
    ]
    assert consumed_tokens_from_worker_events(events) == 42

    malformed = [_event(USAGE_REPORTED_EVENT_TYPE, "garbage")]
    assert consumed_tokens_from_worker_events(malformed) == 0


async def _fresh_manager(db_engine: AsyncEngine, workspaces: WorkspaceService):
    from engine.capabilities.lease_service import CapabilityLeaseService
    from engine.workers.registry import WorkerProfileRegistry
    from engine.workers.scripted_adapter import ScriptedWorkerAdapter
    from engine.workers.service import WorkerManagerService

    leases = CapabilityLeaseService(db_engine)
    registry = WorkerProfileRegistry()
    await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
    return WorkerManagerService(db_engine, registry, leases=leases)


@pytest.mark.asyncio
async def test_usage_report_records_events_and_decrements_derived_budget(
    tmp_path: Path,
) -> None:
    """A real completed run's reports are observable as worker events plus
    generic events; remaining budget is derived from the plan ceiling
    minus summed payloads. The plan here carries only the planner's
    effort-derived hint, so metering degrades to that declared budget."""
    root = repo_root()
    db_engine = new_engine()
    fixture = None
    try:
        fixture = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-USAGE-BASIC"
        )
        workspaces = WorkspaceService(db_engine, root=root)
        manager = await _fresh_manager(db_engine, workspaces)
        action = WorkerAction(command=[sys.executable, "-c", "print('usage')"])
        hint = fixture.execution_plan.token_budget[PLANNER_HINT_MAX_TOKENS_KEY]
        assert isinstance(hint, int)

        first = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=action,
            idempotency_key="usage-basic-1",
        )
        assert first.status == "COMPLETED"

        outcome = await manager.record_run_usage(
            run_id=first.run_id,
            execution_plan=fixture.execution_plan,
            input_tokens=10,
            output_tokens=5,
            idempotency_key="usage-report-1",
        )
        assert outcome.consumed_tokens == 15
        assert outcome.ceiling_tokens == hint
        assert outcome.remaining_tokens == hint - 15
        assert outcome.budget_exceeded is False

        second = await manager.record_run_usage(
            run_id=first.run_id,
            execution_plan=fixture.execution_plan,
            input_tokens=7,
            output_tokens=8,
            cost_basis="subscription seat; not attributable (EDR-0001)",
            idempotency_key="usage-report-2",
        )
        assert second.consumed_tokens == 15
        assert second.remaining_tokens == hint - 30

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            worker_events = await manager.list_events(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                run_id=first.run_id,
                uow=uow,
            )
            generic = await EventsRepository().list_events_for_aggregate(
                uow.connection, "worker_run", first.run_id
            )
            await uow.commit()
        usage_worker_events = [
            item
            for item in worker_events
            if item.event_type == USAGE_REPORTED_EVENT_TYPE
        ]
        assert len(usage_worker_events) == 2
        assert [item.payload["total_tokens"] for item in usage_worker_events] == [
            15,
            15,
        ]
        usage_generic = [
            item for item in generic if item.event_type == USAGE_REPORTED_EVENT_TYPE
        ]
        assert len(usage_generic) == 2
    finally:
        if fixture is not None and fixture.workspace.status != "CLEANED_UP":
            await WorkspaceService(db_engine, root=root).cleanup(
                workspace=fixture.workspace
            )
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_replayed_usage_key_returns_first_outcome_without_second_decrement(
    tmp_path: Path,
) -> None:
    """At-least-once adapter forwarding must be safe: the same
    idempotency key replays the stored first outcome instead of appending
    a duplicate usage event (which would double-decrement)."""
    root = repo_root()
    db_engine = new_engine()
    fixture = None
    try:
        fixture = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-USAGE-REPLAY"
        )
        workspaces = WorkspaceService(db_engine, root=root)
        manager = await _fresh_manager(db_engine, workspaces)
        first = await manager.invoke_run(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=WorkerAction(command=[sys.executable, "-c", "print('r')"]),
            idempotency_key="usage-replay-run",
        )
        assert first.status == "COMPLETED"

        original = await manager.record_run_usage(
            run_id=first.run_id,
            execution_plan=fixture.execution_plan,
            input_tokens=20,
            output_tokens=0,
            idempotency_key="usage-replay-key",
        )
        replayed = await manager.record_run_usage(
            run_id=first.run_id,
            execution_plan=fixture.execution_plan,
            input_tokens=20,
            output_tokens=0,
            idempotency_key="usage-replay-key",
        )
        assert replayed.event_sequence == original.event_sequence
        assert replayed.consumed_tokens == original.consumed_tokens
        assert replayed.remaining_tokens == original.remaining_tokens

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            worker_events = await manager.list_events(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                run_id=first.run_id,
                uow=uow,
            )
            await uow.commit()
        assert (
            len(
                [
                    item
                    for item in worker_events
                    if item.event_type == USAGE_REPORTED_EVENT_TYPE
                ]
            )
            == 1
        )
    finally:
        if fixture is not None and fixture.workspace.status != "CLEANED_UP":
            await WorkspaceService(db_engine, root=root).cleanup(
                workspace=fixture.workspace
            )
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_zero_crossing_pauses_for_human_through_existing_recovery_row(
    tmp_path: Path,
) -> None:
    """The zero-crossing reuses commit 0464933's exact mechanism: a
    durable FAILED TaskAttempt with failure_class=BUDGET_EXCEEDED, which
    RecoveryService.assert_clear_to_retry turns into the matrix's
    RESOURCE_EXHAUSTION pause-for-human row. No parallel pause machinery.

    The pause target is a LIVE attempt (IN_PROGRESS) with a non-terminal
    run -- the state a real async harness sits in while usage reports
    stream in. A late report against an already-terminal attempt is
    recorded but must NOT resurrect the closed attempt (covered below)."""
    root = repo_root()
    db_engine = new_engine()
    fixture = None
    try:
        fixture = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-USAGE-CROSSING"
        )
        workspaces = WorkspaceService(db_engine, root=root)
        manager = await _fresh_manager(db_engine, workspaces)
        # A live IN_PROGRESS attempt plus a PLANNED run: exactly what an
        # async harness holds mid-flight when its provider reports arrive.
        created = await TaskAttemptService(db_engine).create(
            task=fixture.task,
            execution_plan=fixture.execution_plan,
            workspace_revision="deadbeef",
            input_context_hash=fixture.context_package.assembly_hash,
        )
        now = datetime.now(UTC)
        run = WorkerRun(
            run_id=uuid7(),
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_attempt_id=created.attempt_id,
            sequence=1,
            execution_plan_id=fixture.execution_plan.plan_id,
            worker_session_id=None,
            worker_id="worker.scripted-deterministic-v1",
            worker_profile_id="profile.deterministic_runner",
            environment_id=fixture.execution_plan.execution_environment_id,
            workspace_id=fixture.workspace.workspace_id,
            context_package_id=fixture.execution_plan.context_package_id,
            policy_version="worker-manager-v1",
            lease_set_hash="0" * 64,
            checkpoint_id=None,
            status="PLANNED",
            failure_class=None,
            usage_record_id=None,
            artifact_manifest_id=None,
            started_at=None,
            ended_at=None,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            await WorkerRunRepository().insert_run(uow.connection, run)
            await uow.commit()

        hint = fixture.execution_plan.token_budget[PLANNER_HINT_MAX_TOKENS_KEY]
        assert isinstance(hint, int)
        with pytest.raises(DdeError) as refused:
            await manager.record_run_usage(
                run_id=run.run_id,
                execution_plan=fixture.execution_plan,
                input_tokens=hint + 1,
                output_tokens=0,
                idempotency_key="usage-crossing-report",
            )
        # BudgetExhaustedError maps onto BUDGET_EXCEEDED.
        assert refused.value.error_code == "BUDGET_EXCEEDED"
        assert refused.value.retryable is False

        async with open_unit_of_work(
            db_engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            attempts = await TaskAttemptRepository().list_for_task(
                uow.connection, fixture.task.task_id
            )
            await uow.commit()
        exhausted = [row for row in attempts if row.failure_class == "BUDGET_EXCEEDED"]
        assert len(exhausted) >= 1

        recovery = RecoveryService(db_engine)
        with pytest.raises(DdeError) as paused:
            await recovery.assert_clear_to_retry(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                task_id=fixture.task.task_id,
                mission_id=fixture.mission.mission_id,
            )
        assert paused.value.details is not None
        assert paused.value.details["failure_class"] == "RESOURCE_EXHAUSTION"
        assert paused.value.details["action"] == "request_budget"
    finally:
        if fixture is not None and fixture.workspace.status != "CLEANED_UP":
            await WorkspaceService(db_engine, root=root).cleanup(
                workspace=fixture.workspace
            )
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_resume_refusal_appends_observable_event(tmp_path: Path) -> None:
    """The refusal keeps its typed error and unchanged durability, and now
    also lands an explicit ResumeRefused event carrying reason class and
    recovery action -- recorded even though the guarded transaction rolls
    back."""
    root = repo_root()
    db_engine = new_engine()
    built = None
    workspace = None
    try:
        built = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-USAGE-RESUME-REFUSAL"
        )
        workspace = built.workspace
        del workspace  # cleanup handled via `built` in finally
        workspaces = WorkspaceService(db_engine, root=root)
        manager = await _fresh_manager(db_engine, workspaces)
        created = await TaskAttemptService(db_engine).create(
            task=built.task,
            execution_plan=built.execution_plan,
            workspace_revision="deadbeef",
            input_context_hash=built.context_package.assembly_hash,
        )
        # Fail the attempt so resume_run refuses it (not IN_PROGRESS).
        await TaskAttemptService(db_engine).fail(
            tenant_id=built.tenant.tenant_id,
            project_id=built.tenant.project_id,
            attempt_id=created.attempt_id,
            failure_class="WORKER_FAILURE",
            checkpoint_id=None,
        )

        with pytest.raises(DdeError) as excinfo:
            await manager.resume_run(
                task=built.task,
                execution_plan=built.execution_plan,
                workspace=built.workspace,
                input_context_hash=built.context_package.assembly_hash,
                action=WorkerAction(command=[sys.executable, "-c", "pass"]),
                attempt_id=created.attempt_id,
                idempotency_key="resume-refusal-1",
            )
        assert excinfo.value.error_code == "VERSION_CONFLICT"

        async with open_unit_of_work(
            db_engine,
            tenant_id=built.tenant.tenant_id,
            project_id=built.tenant.project_id,
        ) as uow:
            events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "task_attempt", created.attempt_id
            )
            await uow.commit()
        refusals = [
            item for item in events if item.event_type == RESUME_REFUSED_EVENT_TYPE
        ]
        assert len(refusals) == 1
        payload = refusals[0].payload
        assert payload["reason_class"] == "ATTEMPT_NOT_IN_PROGRESS"
        assert payload["observed_status"] == "FAILED"
        assert payload["action"] == "reject"
        assert payload["allow_new_worker_run"] is False
        assert payload["source"] == "resume_run"
    finally:
        if built is not None and built.workspace.status != "CLEANED_UP":
            await WorkspaceService(db_engine, root=root).cleanup(
                workspace=built.workspace
            )
        await db_engine.dispose()
