"""Production Worker Manager (Chapter 8.4) — the sole writer of
`worker_runs`/`worker_events` rows in PostgreSQL (Chapter 3.8).

`WorkerManagerService.invoke_run()` performs Chapter 3.9's steps 8/10 (a
real `TaskAttempt`, then a real `WorkerRun` "created and attached to the
attempt in the SAME transaction") composing `engine.missions.attempts.
TaskAttemptService` and `engine.environments.service.
ExecutionEnvironmentService` under one shared unit of work, exactly as
`engine.execution.service.ExecutionPlanService.plan()` composes
`ExecutionEnvironmentService`/`WorkspaceService` (Chapter 3.5: a transaction
may span module boundaries). It then drives the real `WorkerRun` through
Chapter 8.2's lifecycle by calling a certified `engine.workers.adapter.
WorkerAdapter` (Chapter 8.1) resolved from `engine.workers.registry.
WorkerProfileRegistry` (Chapter 8.4), translating every real transition into
a `WorkerEvent` (Chapter 8.3) and a generic domain event (`engine.events`).

The whole operation is guarded by `engine.events.idempotency.CommandLedger`
(Chapter 3.7, 12.5) on a caller-supplied `idempotency_key`: a repeated
invocation with the same key never creates a second `TaskAttempt` or
`WorkerRun` and never re-executes the worker's action — it returns the
first call's stored, completed `WorkerRun` instead, matching
`engine.governance.records.GovernanceRecords`'s exact pattern.

Deliberately out of Stage 1 scope, per the mission brief: `WorkerSession`
(Chapter 8.6 — `worker_session_id` stays `None`), `CapabilityLease`
issuance (Chapter 9/10, DDE-016/017 — `lease_set_hash` is computed over the
real, currently-empty lease set, not fabricated), checkpoint/pause/resume
(Chapter 8.2's `CHECKPOINTING`/`PAUSING`/`PAUSED`/`RESUMING` branches are
real transitions in `engine.workers.states` but nothing in this mission
drives a run into them — the one certified profile is synchronous), and
`usage_record_id`/`artifact_manifest_id` (no `usage_records`/
`artifact_manifests` table exists in Chapter 3.3's Stage 1 set — the real
usage/artifact data this mission captures lives in the `WorkerEvent`
payloads instead, exactly as `ExecutionPlanService` leaves
`verification_plan_id`/`acceptance_oracle_id` `None` for concepts Stage 1
has not built a table for).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.task import Task
from engine.contracts.worker_event import WorkerEvent
from engine.contracts.worker_run import WorkerRun
from engine.contracts.workspace import Workspace
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.environments.service import ExecutionEnvironmentService
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.missions.attempts import TaskAttemptService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.workers.adapter import (
    ActionBindableWorkerAdapter,
    WorkerAction,
    WorkerAdapter,
)
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.repository import WorkerEventRepository, WorkerRunRepository
from engine.workers.states import TERMINAL_STATES, WORKER_RUN_TRANSITIONS

T = TypeVar("T")

#: Chapter 8's Worker Manager has no separate `policy_version` concept of
#: its own the way `engine.routing.policy.POLICY_VERSION` does for routing
#: (Chapter 6.2) — this is the Stage 1 constant for whichever binding/
#: certification policy this Worker Manager enforces (currently: "a profile
#: must be registered and healthy"), versioned so a future policy change is
#: observable on every `WorkerRun` it stamped.
WORKER_MANAGER_POLICY_VERSION = "worker-manager-v1"

#: No `CapabilityLease` exists yet (Chapter 9/10, DDE-016/017) — this is a
#: real hash of the real, currently-empty lease set, not a fabricated
#: value. Once leases exist, `lease_set_hash` must hash the real granted
#: set instead.
EMPTY_LEASE_SET_HASH = sha256_hex(canonical_json([]))

WORKER_PREPARE_FAILED = "WORKER_PREPARE_FAILED"
WORKER_COMMAND_FAILED = "WORKER_COMMAND_FAILED"
WORKER_COMMAND_TIMEOUT = "WORKER_COMMAND_TIMEOUT"


def _invoke_request_hash(
    *,
    task_id: UUID,
    execution_plan_id: UUID,
    workspace_id: UUID,
    action: WorkerAction,
) -> str:
    return sha256_hex(
        canonical_json(
            {
                "task_id": str(task_id),
                "execution_plan_id": str(execution_plan_id),
                "workspace_id": str(workspace_id),
                "command": list(action.command),
                "write_files": {
                    path: content.hex()
                    for path, content in sorted(action.write_files.items())
                },
            }
        )
    )


class WorkerManagerService:
    """Async, PostgreSQL-backed writer for `worker_runs`/`worker_events`
    (Chapter 3.8). `invoke_run` opens and commits its own unit of work
    unless one is supplied, so a caller composing a cross-module
    transaction (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        registry: WorkerProfileRegistry,
        events: EventService | None = None,
        commands: CommandLedger | None = None,
        run_repository: WorkerRunRepository | None = None,
        event_repository: WorkerEventRepository | None = None,
        environments: ExecutionEnvironmentService | None = None,
        attempts: TaskAttemptService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._registry = registry
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
        self._run_repository = run_repository or WorkerRunRepository()
        self._event_repository = event_repository or WorkerEventRepository()
        self._environments = environments or ExecutionEnvironmentService(
            engine, events=self._events
        )
        self._attempts = attempts or TaskAttemptService(engine, events=self._events)
        self._clock = clock or SystemClock()

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await body(owned)
            await owned.commit()
            return result

    async def invoke_run(
        self,
        *,
        task: Task,
        execution_plan: ExecutionPlan,
        workspace: Workspace,
        input_context_hash: str,
        action: WorkerAction,
        idempotency_key: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> WorkerRun:
        """Chapter 3.9 steps 8/10 plus Chapter 8.2's full drive to a
        terminal state, guarded end-to-end by `idempotency_key`."""
        if execution_plan.task_id != task.task_id:
            raise DdeError(
                "POLICY_DENIED",
                "ExecutionPlan does not belong to this task",
                details={
                    "task_id": str(task.task_id),
                    "plan_task_id": str(execution_plan.task_id),
                },
            )
        if (
            workspace.execution_environment_id
            != execution_plan.execution_environment_id
        ):
            raise DdeError(
                "POLICY_DENIED",
                "Workspace is not bound to this plan's execution environment",
                details={
                    "workspace_environment_id": str(workspace.execution_environment_id),
                    "plan_environment_id": str(execution_plan.execution_environment_id),
                },
            )

        tenant_id = execution_plan.tenant_id
        project_id = execution_plan.project_id
        request_hash = _invoke_request_hash(
            task_id=task.task_id,
            execution_plan_id=execution_plan.plan_id,
            workspace_id=workspace.workspace_id,
            action=action,
        )

        async def _op(active: PostgresUnitOfWork) -> WorkerRun:
            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                uow=active,
            )
            if not is_new:
                return self._replay_or_raise(record)

            environment = await self._environments.get_environment(
                tenant_id=tenant_id,
                project_id=project_id,
                environment_id=execution_plan.execution_environment_id,
                uow=active,
            )
            self._environments.assert_schedulable(environment)

            adapter = self._registry.get_certified_adapter(
                execution_plan.worker_profile_id
            )
            registration = await adapter.register()

            attempt = await self._attempts.create(
                task=task,
                execution_plan=execution_plan,
                workspace_revision=workspace.current_revision
                or workspace.base_revision
                or "unknown",
                input_context_hash=input_context_hash,
                uow=active,
            )

            sequence = await self._run_repository.next_sequence(
                active.connection, attempt.attempt_id
            )
            now = self._clock.now()
            run = WorkerRun(
                run_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=execution_plan.mission_id,
                task_attempt_id=attempt.attempt_id,
                sequence=sequence,
                execution_plan_id=execution_plan.plan_id,
                worker_session_id=None,
                worker_id=registration.worker_id,
                worker_profile_id=execution_plan.worker_profile_id,
                environment_id=execution_plan.execution_environment_id,
                workspace_id=workspace.workspace_id,
                context_package_id=execution_plan.context_package_id,
                policy_version=WORKER_MANAGER_POLICY_VERSION,
                lease_set_hash=EMPTY_LEASE_SET_HASH,
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
            await self._run_repository.insert_run(active.connection, run)
            await self._append_worker_event(
                active,
                run,
                task_id=task.task_id,
                event_type="WorkerRunCreated",
                payload={
                    "worker_id": run.worker_id,
                    "worker_profile_id": run.worker_profile_id,
                },
            )
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="WorkerRunCreated",
                aggregate_type="worker_run",
                aggregate_id=run.run_id,
                mission_id=run.mission_id,
                task_id=task.task_id,
                payload={
                    "task_attempt_id": str(attempt.attempt_id),
                    "worker_profile_id": run.worker_profile_id,
                },
                uow=active,
            )

            run = await self._drive_lifecycle(
                active,
                run,
                adapter=adapter,
                execution_plan=execution_plan,
                workspace=workspace,
                action=action,
                task_id=task.task_id,
            )

            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=run.model_dump(mode="json"),
                uow=active,
            )
            return run

        return await self._run(uow, tenant_id, project_id, _op)

    async def _drive_lifecycle(
        self,
        active: PostgresUnitOfWork,
        run: WorkerRun,
        *,
        adapter: WorkerAdapter,
        execution_plan: ExecutionPlan,
        workspace: Workspace,
        action: WorkerAction,
        task_id: UUID,
    ) -> WorkerRun:
        if isinstance(adapter, ActionBindableWorkerAdapter):
            adapter.bind_action(execution_plan.plan_id, action)

        run = await self._transition(
            active,
            run,
            "PREPARING",
            task_id=task_id,
            event_type="WorkerRunPreparing",
            payload={},
        )
        try:
            prepared = await adapter.prepare(
                execution_plan=execution_plan,
                context_ref=execution_plan.context_package_id,
                env_ref=workspace,
            )
        except DdeError as exc:
            return await self._fail(
                active,
                run,
                task_id=task_id,
                failure_class=WORKER_PREPARE_FAILED,
                payload={"error_code": exc.error_code, "message": exc.message},
            )

        run = await self._transition(
            active,
            run,
            "READY",
            task_id=task_id,
            event_type="WorkerRunReady",
            payload={"detail": prepared.detail},
        )
        run = await self._transition(
            active,
            run,
            "RUNNING",
            task_id=task_id,
            event_type="WorkerRunStarted",
            payload={},
        )

        handle = await adapter.start(run)

        if handle.exit_code == 0 and not handle.timed_out:
            return await self._transition(
                active,
                run,
                "COMPLETED",
                task_id=task_id,
                event_type="WorkerRunCompleted",
                payload={
                    "exit_code": handle.exit_code,
                    "stdout": handle.stdout,
                    "stderr": handle.stderr,
                    "duration_ms": handle.duration_ms,
                    "changed_files": list(handle.changed_files),
                    "diff_text": handle.diff_text,
                },
            )

        failure_class = (
            WORKER_COMMAND_TIMEOUT if handle.timed_out else WORKER_COMMAND_FAILED
        )
        return await self._fail(
            active,
            run,
            task_id=task_id,
            failure_class=failure_class,
            payload={
                "exit_code": handle.exit_code,
                "stdout": handle.stdout,
                "stderr": handle.stderr,
                "duration_ms": handle.duration_ms,
                "timed_out": handle.timed_out,
            },
        )

    async def _transition(
        self,
        active: PostgresUnitOfWork,
        run: WorkerRun,
        target_status: str,
        *,
        task_id: UUID,
        event_type: str,
        payload: dict[str, object],
    ) -> WorkerRun:
        next_status = transition(run.status, target_status, WORKER_RUN_TRANSITIONS)
        now = self._clock.now()
        fields: dict[str, object] = {"status": next_status, "updated_at": now}
        if next_status == "RUNNING" and run.started_at is None:
            fields["started_at"] = now
        if next_status in TERMINAL_STATES:
            fields["ended_at"] = now
        rowcount = await self._run_repository.update_run(
            active.connection, run.run_id, fields=fields
        )
        if rowcount != 1:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown worker run",
                details={"run_id": str(run.run_id)},
            )
        updated = await self._require_run(active, run.run_id)
        await self._append_worker_event(
            active, updated, task_id=task_id, event_type=event_type, payload=payload
        )
        await self._events.append(
            tenant_id=updated.tenant_id,
            project_id=updated.project_id,
            event_type=event_type,
            aggregate_type="worker_run",
            aggregate_id=updated.run_id,
            mission_id=updated.mission_id,
            task_id=task_id,
            payload=payload,
            uow=active,
        )
        return updated

    async def _fail(
        self,
        active: PostgresUnitOfWork,
        run: WorkerRun,
        *,
        task_id: UUID,
        failure_class: str,
        payload: dict[str, object],
    ) -> WorkerRun:
        next_status = transition(run.status, "FAILED", WORKER_RUN_TRANSITIONS)
        now = self._clock.now()
        fields: dict[str, object] = {
            "status": next_status,
            "failure_class": failure_class,
            "ended_at": now,
            "updated_at": now,
        }
        rowcount = await self._run_repository.update_run(
            active.connection, run.run_id, fields=fields
        )
        if rowcount != 1:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown worker run",
                details={"run_id": str(run.run_id)},
            )
        updated = await self._require_run(active, run.run_id)
        full_payload = {**payload, "failure_class": failure_class}
        await self._append_worker_event(
            active,
            updated,
            task_id=task_id,
            event_type="WorkerRunFailed",
            payload=full_payload,
        )
        await self._events.append(
            tenant_id=updated.tenant_id,
            project_id=updated.project_id,
            event_type="WorkerRunFailed",
            aggregate_type="worker_run",
            aggregate_id=updated.run_id,
            mission_id=updated.mission_id,
            task_id=task_id,
            payload=full_payload,
            uow=active,
        )
        return updated

    async def _append_worker_event(
        self,
        active: PostgresUnitOfWork,
        run: WorkerRun,
        *,
        task_id: UUID,
        event_type: str,
        payload: dict[str, object],
    ) -> WorkerEvent:
        sequence = await self._event_repository.next_sequence(
            active.connection, run.run_id
        )
        now = self._clock.now()
        correlation_id = str(run.run_id)
        integrity_hash = sha256_hex(
            canonical_json(
                {
                    "run_id": str(run.run_id),
                    "sequence": sequence,
                    "event_type": event_type,
                    "payload": payload,
                }
            )
        )
        event = WorkerEvent(
            event_id=uuid7(),
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            mission_id=run.mission_id,
            run_id=run.run_id,
            task_id=task_id,
            sequence=sequence,
            event_type=event_type,
            occurred_at=now,
            actor="worker_manager",
            correlation_id=correlation_id,
            causation_id=None,
            payload=payload,
            schema_version="1",
            integrity_hash=integrity_hash,
            created_at=now,
            updated_at=now,
        )
        await self._event_repository.insert_event(active.connection, event)
        return event

    def _replay_or_raise(self, record: CommandIdempotency) -> WorkerRun:
        if record.status == "completed" and record.result is not None:
            return WorkerRun.model_validate(record.result)
        if record.status == "failed":
            raise DdeError(
                "VERSION_CONFLICT",
                "Command previously failed; refusing to re-execute",
                details={"idempotency_key": record.idempotency_key},
            )
        raise DdeError(
            "VERSION_CONFLICT",
            "Command is already in progress",
            retryable=True,
            details={"idempotency_key": record.idempotency_key},
        )

    async def get_run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        run_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> WorkerRun:
        async def _op(active: PostgresUnitOfWork) -> WorkerRun:
            return await self._require_run(active, run_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_events(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        run_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[WorkerEvent]:
        async def _op(active: PostgresUnitOfWork) -> list[WorkerEvent]:
            return await self._event_repository.list_for_run(active.connection, run_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def _require_run(self, active: PostgresUnitOfWork, run_id: UUID) -> WorkerRun:
        record = await self._run_repository.get_run(active.connection, run_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown worker run")
        return record
