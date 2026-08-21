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

**DDE-017 addition.** `invoke_run()` now requests and grants a real
`CapabilityLease` (`engine.capabilities.lease_service.
CapabilityLeaseService`) for every concrete Stage 1 side effect the bound
`ScriptedWorkerAdapter.start()` call will actually perform for this
specific `action` -- `capability.run_local_process` always, plus
`capability.workspace_filesystem`/`capability.git_operations` when
`action.write_files` is non-empty -- bound to the real `run.run_id`, before
driving the lifecycle. This is the resolution the mission brief for DDE-016
explicitly deferred ("nothing reads `capability_requirements` and resolves
it against this table"): note it resolves against the *concrete side
effects this action will perform*, not against `ExecutionPlan.
capability_requirements[]` (routing's `capability.repository`/
`capability.testing` tags are a different, `engine.routing.policy`-owned
namespace -- see `engine.capabilities.service`'s module docstring -- and
resolving that separate namespace is out of this mission's scope). A
denied lease is not raised here; it surfaces naturally when `adapter.
start()` calls `require_active` and fails closed, which `_drive_lifecycle`
now catches and captures as a durable `WORKER_CAPABILITY_DENIED` `FAILED`
run rather than losing it to a rolled-back transaction. Once the run
reaches a terminal state, every lease it was granted is consumed
(`CapabilityLeaseService.consume_all_for_run`, Chapter 9.2's `ACTIVE ->
CONSUMED`).

Each `leases.request()` call here deliberately runs in its own, separately
committed unit of work rather than sharing `active` (the still-open
transaction created the `WorkerRun` row): `adapter.start()` -- invoked
later, still inside `active` -- calls `require_active()` on its own,
different connection (Chapter 7.2's guard has no access to a caller's
in-flight transaction), and PostgreSQL's READ COMMITTED isolation only
ever sees data another transaction has *committed*, never another
transaction's uncommitted writes. Granting the lease inside `active` and
checking it from a second connection before `active` commits would
therefore always fail closed on a lease that was, in fact, really granted
-- a false negative, not the real Chapter 9.2 decision. `consume_all_for_run`
does not need the same treatment: it runs after `require_active` has
already committed the `ACTIVE` transition it read, so `active`'s own
statement-level READ COMMITTED snapshot sees it.

`lease_set_hash` still stays `EMPTY_LEASE_SET_HASH`, even after this
mission: Chapter 3.9 step 11 issues leases bound to a `worker_run_id`
*after* step 10 already created that run, so the real granted set cannot
be known yet at the moment this field is written; recomputing it from the
now-real leases once granted would need either a second row update after
`request()` or reordering creation, neither of which this mission's scope
covers.

**DDE-020 correction.** Before inserting a new `WorkerRun`, `invoke_run`
queries live `external_effects` for the `run_local_process` logical scope
and raises `EFFECT_CONFLICT` if an unreconciled `SENT`/`UNKNOWN`/
`RECONCILING` row (or a verified-present `RECONCILED` row) exists -- a new
idempotency key does not bypass Chapter 12.4. A subprocess timeout is
classified as `SIDE_EFFECT_UNKNOWN` (Chapter 12.3), not only
`WORKER_COMMAND_TIMEOUT`. `WORKER_COMMAND_TIMEOUT` remains defined for
payload/legacy readers but is no longer the timeout failure_class.

**DDE-023.** After a terminal run, `invoke_run` records a Chapter 12.1
checkpoint, commits attempt results (or fails the attempt), and stamps
`checkpoint_id` on the run. `invoke_run` refuses a new attempt when a
COMPLETED attempt or COMPLETED WorkerRun already exists for the task, and
refuses a mutation listed in the latest valid checkpoint's `do_not_repeat`.
`resume_run` creates a new WorkerRun on the same IN_PROGRESS attempt
(Chapter 3.9 1:N) after a non-terminal predecessor. Chapter 12.3
(`RecoveryService.assert_clear_to_retry`) runs before a new attempt:
AUTHORIZATION/SCOPE/WRONG_PRODUCT/SPECIFICATION/DRIFT never silent-retry;
WORKER_FAILURE allows one recover then reroute. Chapter 12.4
`assert_clear_to_mutate` still runs first so UNKNOWN is never
matrix-retried around the journal.

Deliberately out of this mission: `WorkerSession`
(Chapter 8.6 — `worker_session_id` stays `None`), checkpoint/pause/resume
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

from engine.capabilities.lease_service import CapabilityLeaseService
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
from engine.recovery.checkpoint_service import (
    CheckpointService,
    do_not_repeat_from_effects,
)
from engine.recovery.dispatch import RecoveryService
from engine.recovery.replay import MUTATION_ALREADY_DONE, ReplayService
from engine.recovery.scope import (
    LOCAL_PROCESS_SYSTEM,
    local_process_operation,
    local_process_resource,
)
from engine.recovery.service import EFFECT_CONFLICT, ExternalEffectService
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
WORKER_FAILURE = "WORKER_FAILURE"
WORKER_CAPABILITY_DENIED = "WORKER_CAPABILITY_DENIED"
#: Chapter 12.3 -- subprocess timeout of a journaled side effect is not
#: classified as a generic command timeout alone; recovery dispatches on
#: this class ("Reconcile before any retry").
SIDE_EFFECT_UNKNOWN = "SIDE_EFFECT_UNKNOWN"

#: DDE-016's real, seeded `capability_id`s -- see the module docstring's
#: DDE-017 addition for which of these a given `action` actually needs.
CAPABILITY_RUN_LOCAL_PROCESS = "capability.run_local_process"
CAPABILITY_WORKSPACE_FILESYSTEM = "capability.workspace_filesystem"
CAPABILITY_GIT_OPERATIONS = "capability.git_operations"


def _required_capability_ids(action: WorkerAction) -> tuple[str, ...]:
    """The exact, concrete `capability_id`s this action's real `start()`
    call will exercise (see `ScriptedWorkerAdapter.start`): a subprocess
    execution always, plus a workspace write and its git status snapshot
    only when the action actually writes files."""
    if action.write_files:
        return (
            CAPABILITY_WORKSPACE_FILESYSTEM,
            CAPABILITY_GIT_OPERATIONS,
            CAPABILITY_RUN_LOCAL_PROCESS,
        )
    return (CAPABILITY_RUN_LOCAL_PROCESS,)


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
        leases: CapabilityLeaseService | None = None,
        effects: ExternalEffectService | None = None,
        checkpoints: CheckpointService | None = None,
        replay: ReplayService | None = None,
        recovery: RecoveryService | None = None,
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
        self._leases = leases or CapabilityLeaseService(
            engine, events=self._events, clock=self._clock
        )
        self._effects = effects or ExternalEffectService(
            engine, events=self._events, clock=self._clock
        )
        self._checkpoints = checkpoints or CheckpointService(
            engine, events=self._events, clock=self._clock
        )
        self._replay = replay or ReplayService(
            engine,
            checkpoints=self._checkpoints,
            attempts=self._attempts,
            clock=self._clock,
        )
        self._recovery = recovery or RecoveryService(
            engine,
            events=self._events,
            commands=self._commands,
            attempts=self._attempts,
            checkpoints=self._checkpoints,
            effects=self._effects,
        )

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

            await self._replay.assert_clear_to_start_attempt(
                tenant_id=tenant_id,
                project_id=project_id,
                task_id=task.task_id,
                target_system=LOCAL_PROCESS_SYSTEM,
                target_resource=local_process_resource(workspace),
                operation=local_process_operation(action.command),
                uow=active,
            )
            await self._effects.assert_clear_to_mutate(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=execution_plan.mission_id,
                target_system=LOCAL_PROCESS_SYSTEM,
                target_resource=local_process_resource(workspace),
                operation=local_process_operation(action.command),
                uow=active,
            )
            retry_of = await self._recovery.assert_clear_to_retry(
                tenant_id=tenant_id,
                project_id=project_id,
                task_id=task.task_id,
                mission_id=execution_plan.mission_id,
                uow=active,
            )

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
                retry_of=retry_of,
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

            for capability_id in _required_capability_ids(action):
                # No `uow=active`: see the module docstring -- this must be
                # a real, separately committed transaction so the lease is
                # actually visible to `require_active()`'s own connection
                # inside `adapter.start()`, called later still within
                # `active`'s own open transaction.
                await self._leases.request(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=run.mission_id,
                    task_id=task.task_id,
                    execution_plan_id=execution_plan.plan_id,
                    worker_run_id=run.run_id,
                    environment_id=execution_plan.execution_environment_id,
                    capability_id=capability_id,
                    capability_version="1",
                    requested_by="engine.workers.service.WorkerManagerService",
                    idempotency_key=f"{run.run_id}:{capability_id}",
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
            run = await self._checkpoint_terminal_run(
                active,
                run,
                task_id=task.task_id,
                workspace_revision=workspace.current_revision
                or workspace.base_revision
                or "unknown",
            )

            await self._leases.consume_all_for_run(
                tenant_id=tenant_id,
                project_id=project_id,
                worker_run_id=run.run_id,
                uow=active,
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

    async def resume_run(
        self,
        *,
        task: Task,
        execution_plan: ExecutionPlan,
        workspace: Workspace,
        input_context_hash: str,
        action: WorkerAction,
        attempt_id: UUID,
        idempotency_key: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> WorkerRun:
        """Chapter 3.9 1:N recovery: a new WorkerRun on an existing
        IN_PROGRESS attempt. Does not create a second attempt.
        """
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

            attempt = await self._attempts.get_attempt(
                tenant_id=tenant_id,
                project_id=project_id,
                attempt_id=attempt_id,
                uow=active,
            )
            if attempt.task_id != task.task_id:
                raise DdeError(
                    "POLICY_DENIED",
                    "TaskAttempt does not belong to this task",
                    details={"attempt_id": str(attempt_id)},
                )
            if attempt.status != "IN_PROGRESS":
                raise DdeError(
                    "VERSION_CONFLICT",
                    "resume_run requires an IN_PROGRESS attempt",
                    details={"status": attempt.status},
                )

            await self._replay.assert_clear_to_start_attempt(
                tenant_id=tenant_id,
                project_id=project_id,
                task_id=task.task_id,
                target_system=LOCAL_PROCESS_SYSTEM,
                target_resource=local_process_resource(workspace),
                operation=local_process_operation(action.command),
                uow=active,
            )
            await self._refuse_completed_worker_result(
                active, tenant_id=tenant_id, project_id=project_id, task_id=task.task_id
            )
            await self._effects.assert_clear_to_mutate(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=execution_plan.mission_id,
                target_system=LOCAL_PROCESS_SYSTEM,
                target_resource=local_process_resource(workspace),
                operation=local_process_operation(action.command),
                uow=active,
            )

            prior_runs = await self._run_repository.list_for_attempt(
                active.connection, attempt.attempt_id
            )
            if prior_runs and prior_runs[-1].status not in TERMINAL_STATES:
                await self._fail(
                    active,
                    prior_runs[-1],
                    task_id=task.task_id,
                    failure_class=WORKER_FAILURE,
                    payload={"reason": "replaced_by_resume_run"},
                )

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
                checkpoint_id=attempt.checkpoint_id,
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
                    "resume_of_attempt": str(attempt.attempt_id),
                },
            )
            for capability_id in _required_capability_ids(action):
                await self._leases.request(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=run.mission_id,
                    task_id=task.task_id,
                    execution_plan_id=execution_plan.plan_id,
                    worker_run_id=run.run_id,
                    environment_id=execution_plan.execution_environment_id,
                    capability_id=capability_id,
                    capability_version="1",
                    requested_by="engine.workers.service.WorkerManagerService",
                    idempotency_key=f"{run.run_id}:{capability_id}",
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
            run = await self._checkpoint_terminal_run(
                active,
                run,
                task_id=task.task_id,
                workspace_revision=workspace.current_revision
                or workspace.base_revision
                or input_context_hash,
            )
            await self._leases.consume_all_for_run(
                tenant_id=tenant_id,
                project_id=project_id,
                worker_run_id=run.run_id,
                uow=active,
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

    async def _refuse_completed_worker_result(
        self,
        active: PostgresUnitOfWork,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID,
    ) -> None:
        attempts = await self._attempts.list_for_task(
            tenant_id=tenant_id,
            project_id=project_id,
            task_id=task_id,
            uow=active,
        )
        for attempt in attempts:
            runs = await self._run_repository.list_for_attempt(
                active.connection, attempt.attempt_id
            )
            completed = [item for item in runs if item.status == "COMPLETED"]
            if completed:
                raise DdeError(
                    MUTATION_ALREADY_DONE,
                    "Refusing to re-run a task whose WorkerRun already "
                    f"COMPLETED (run_id={completed[0].run_id})",
                    retryable=False,
                    details={
                        "task_id": str(task_id),
                        "run_id": str(completed[0].run_id),
                    },
                )

    async def _checkpoint_terminal_run(
        self,
        active: PostgresUnitOfWork,
        run: WorkerRun,
        *,
        task_id: UUID,
        workspace_revision: str,
    ) -> WorkerRun:
        effects = await self._effects.list_for_run(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            worker_run_id=run.run_id,
            uow=active,
        )
        leases = await self._leases.list_for_run(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            worker_run_id=run.run_id,
            uow=active,
        )
        events = await self._event_repository.list_for_run(
            active.connection, run.run_id
        )
        sequence = events[-1].sequence if events else 0
        completed = [str(task_id)] if run.status == "COMPLETED" else []
        pending = [] if run.status == "COMPLETED" else [str(task_id)]
        failures = [run.failure_class] if run.failure_class else []
        next_action = "verify" if run.status == "COMPLETED" else "recover"
        checkpoint = await self._checkpoints.record(
            run=run,
            task_id=task_id,
            workspace_revision=workspace_revision,
            event_sequence=sequence,
            completed_work=completed,
            verified_work=[],
            pending_work=pending,
            known_failures=failures,
            next_action=next_action,
            do_not_repeat=do_not_repeat_from_effects(effects),
            artifact_refs=[],
            lease_refs=[item.lease_id for item in leases],
            idempotency_key=f"{run.run_id}:checkpoint",
            uow=active,
        )
        now = self._clock.now()
        await self._run_repository.update_run(
            active.connection,
            run.run_id,
            fields={"checkpoint_id": checkpoint.checkpoint_id, "updated_at": now},
        )
        updated = await self._require_run(active, run.run_id)
        if run.status == "COMPLETED":
            await self._attempts.commit_results(
                tenant_id=run.tenant_id,
                project_id=run.project_id,
                attempt_id=run.task_attempt_id,
                result_artifact_refs=[],
                checkpoint_id=checkpoint.checkpoint_id,
                uow=active,
            )
        elif run.status == "FAILED":
            await self._attempts.fail(
                tenant_id=run.tenant_id,
                project_id=run.project_id,
                attempt_id=run.task_attempt_id,
                failure_class=run.failure_class or WORKER_FAILURE,
                checkpoint_id=checkpoint.checkpoint_id,
                uow=active,
            )
        return updated

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

        try:
            handle = await adapter.start(run)
        except DdeError as exc:
            failure_class = (
                SIDE_EFFECT_UNKNOWN
                if exc.error_code == EFFECT_CONFLICT
                else WORKER_CAPABILITY_DENIED
            )
            return await self._fail(
                active,
                run,
                task_id=task_id,
                failure_class=failure_class,
                payload={"error_code": exc.error_code, "message": exc.message},
            )

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
            SIDE_EFFECT_UNKNOWN if handle.timed_out else WORKER_COMMAND_FAILED
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
                "timeout_signal": WORKER_COMMAND_TIMEOUT if handle.timed_out else None,
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
