"""Production Chapter 12.3 dispatch + Chapter 4.6 replan (DDE-024).

**Call sites.** `WorkerManagerService.invoke_run` calls
`assert_clear_to_retry` before inserting a WorkerRun. `MissionWorkflowService.retry`
dispatches on failure class. `IntegrationQueueService` consults `decide()`
on CONFLICT. `VerificationRunnerService` fails the TaskAttempt on
VERIFICATION_FAILURE.

**Deferred.** Context critic recompile (DDE-031), alternate adapters
(DDE-025, now present), automatic git revert commits (Ch.10.7 --
REVERT without a supplied revert task is refused), workspace discard plus
write-scope lease release after RETIRE (leases stay held), WorkerRun
cancel/pause for asynchronous harnesses, environment replacement before
ENVIRONMENT_FAILURE resume.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.checkpoint import Checkpoint
from engine.contracts.external_effect import ExternalEffect
from engine.contracts.replan_decision import ReplanDecision
from engine.contracts.task import Task
from engine.contracts.task_attempt import TaskAttempt
from engine.contracts.task_graph import TaskGraph
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.contracts.worker_run import WorkerRun
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.core.ids import uuid7
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.integration.service import WriteScopeLeaseService
from engine.missions.attempts import TaskAttemptService
from engine.missions.service import MissionService
from engine.planning.planner import PLANNER_POLICY_VERSION
from engine.planning.service import TaskGraphService
from engine.recovery.checkpoint_service import (
    CheckpointService,
    do_not_repeat_from_effects,
)
from engine.recovery.matrix import (
    RecoveryDecision,
    classify_dispositions,
    decide,
)
from engine.recovery.service import ExternalEffectService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.verification.repository import VerificationRunRepository
from engine.workers.repository import WorkerEventRepository, WorkerRunRepository

T = TypeVar("T")

_TERMINAL_RUNS = frozenset({"COMPLETED", "FAILED", "CANCELLED"})


class RecoveryService:
    """PostgreSQL dispatcher for the Chapter 12.3 matrix and Chapter 4.6 replan."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        commands: CommandLedger | None = None,
        attempts: TaskAttemptService | None = None,
        checkpoints: CheckpointService | None = None,
        effects: ExternalEffectService | None = None,
        missions: MissionService | None = None,
        graphs: TaskGraphService | None = None,
        leases: WriteScopeLeaseService | None = None,
        runs: WorkerRunRepository | None = None,
        worker_events: WorkerEventRepository | None = None,
        verifications: VerificationRunRepository | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
        self._attempts = attempts or TaskAttemptService(engine, events=self._events)
        self._checkpoints = checkpoints or CheckpointService(
            engine, events=self._events
        )
        self._effects = effects or ExternalEffectService(
            engine, events=self._events, commands=self._commands
        )
        self._missions = missions or MissionService(engine, self._events)
        self._graphs = graphs or TaskGraphService(engine)
        self._leases = leases or WriteScopeLeaseService(engine, events=self._events)
        self._runs = runs or WorkerRunRepository()
        self._worker_events = worker_events or WorkerEventRepository()
        self._verifications = verifications or VerificationRunRepository()

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

    async def assert_clear_to_retry(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID,
        mission_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> UUID | None:
        """Refuse a new WorkerRun the matrix does not permit. Returns the
        FAILED attempt to set as `retry_of`, or None for a first attempt.
        """

        async def _op(active: PostgresUnitOfWork) -> UUID | None:
            current = await self._missions.get_task(
                tenant_id=tenant_id,
                project_id=project_id,
                task_id=task_id,
                uow=active,
            )
            if current.status in {"SUPERSEDED", "RETIRED"}:
                raise DdeError(
                    "POLICY_DENIED",
                    "Refusing a WorkerRun on a SUPERSEDED or RETIRED task",
                    retryable=False,
                    details={
                        "task_id": str(task_id),
                        "status": current.status,
                    },
                )
            attempts = await self._attempts.list_for_task(
                tenant_id=tenant_id,
                project_id=project_id,
                task_id=task_id,
                uow=active,
            )
            failed = [row for row in attempts if row.status == "FAILED"]
            verification_failures = await self._count_verification_failures(
                active, task_id
            )
            if not failed and verification_failures == 0:
                return None
            if failed:
                lead = failed[-1]
                canonical = decide(
                    lead.failure_class or "WORKER_FAILURE", occurrence_count=1
                ).failure_class
                count = sum(
                    1
                    for row in failed
                    if decide(
                        row.failure_class or "WORKER_FAILURE", occurrence_count=1
                    ).failure_class
                    == canonical
                )
                unreconciled = False
                if canonical == "SIDE_EFFECT_UNKNOWN":
                    blocking = await self._effects.list_unreconciled(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        mission_id=mission_id,
                        uow=active,
                    )
                    runs = await self._runs.list_for_mission(
                        active.connection, mission_id
                    )
                    unknown_tasks = self._tasks_for_effects(
                        blocking,
                        runs=runs,
                        attempts={item.attempt_id: item for item in attempts},
                    )
                    unreconciled = task_id in unknown_tasks
                decision = decide(
                    canonical, occurrence_count=count, unreconciled=unreconciled
                )
                self._raise_unless_allowed(decision)
                return lead.attempt_id
            decision = decide(
                "VERIFICATION_FAILURE", occurrence_count=verification_failures
            )
            self._raise_unless_allowed(decision)
            in_progress = [row for row in attempts if row.status == "IN_PROGRESS"]
            return in_progress[-1].attempt_id if in_progress else None

        return await self._run(uow, tenant_id, project_id, _op)

    def decision_for_policy(
        self, *, failure_class: str, occurrence_count: int = 1
    ) -> RecoveryDecision:
        return decide(failure_class, occurrence_count=occurrence_count)

    async def replan(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        graph_id: UUID,
        trigger: str,
        created_by_principal: UUID,
        approved_requirement_slugs: set[str],
        idempotency_key: str,
        revert_tasks: Sequence[Task] = (),
        replacement_tasks: Sequence[Task] = (),
        replacement_edges: Sequence[TaskGraphEdge] = (),
        retire_task_ids: Sequence[UUID] = (),
        uow: PostgresUnitOfWork | None = None,
    ) -> tuple[ReplanDecision, TaskGraph]:
        """Chapter 4.6 production replan."""

        async def _op(active: PostgresUnitOfWork) -> tuple[ReplanDecision, TaskGraph]:
            request_hash = sha256_hex(
                canonical_json(
                    {
                        "graph_id": str(graph_id),
                        "trigger": trigger,
                        "mission_id": str(mission_id),
                    }
                )
            )
            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                uow=active,
            )
            if not is_new:
                if record.status == "completed" and record.result is not None:
                    decision = ReplanDecision.model_validate(record.result["decision"])
                    graph = TaskGraph.model_validate(record.result["graph"])
                    return decision, graph
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Replan command is already in progress or previously failed",
                    retryable=record.status != "failed",
                    details={"idempotency_key": idempotency_key},
                )

            tasks = await self._missions.list_tasks_for_graph(
                tenant_id=tenant_id,
                project_id=project_id,
                graph_id=graph_id,
                uow=active,
            )
            attempts = await self._attempts.list_for_mission(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                uow=active,
            )
            runs = await self._runs.list_for_mission(active.connection, mission_id)
            attempt_by_id = {item.attempt_id: item for item in attempts}
            in_flight, completed, integrated = self._node_sets(
                tasks, attempts=attempts, runs=runs
            )
            blocking = await self._effects.list_unreconciled(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                uow=active,
            )
            unknown_tasks = self._tasks_for_effects(
                blocking, runs=runs, attempts=attempt_by_id
            )
            affected = {task.task_id for task in tasks}
            if unknown_tasks & affected:
                raise DdeError(
                    "EFFECT_UNKNOWN",
                    "Replanning refused until unreconciled external effects "
                    "are resolved",
                    retryable=False,
                    details={
                        "task_ids": [str(item) for item in sorted(unknown_tasks)],
                    },
                )

            dispositions, explanations = classify_dispositions(
                task_ids=[task.task_id for task in tasks],
                statuses={task.task_id: task.status for task in tasks},
                in_flight_ids=in_flight,
                completed_ids=completed,
                integrated_ids=integrated,
                trigger=trigger,
                retire_ids=set(retire_task_ids),
            )
            revert_needed = [
                key for key, disp in dispositions.items() if disp == "REVERT"
            ]
            if revert_needed and not revert_tasks:
                raise DdeError(
                    "POLICY_DENIED",
                    "REVERT requires an explicit revert task (Chapter 10.7); "
                    "refusing to invent a history rewrite",
                    retryable=False,
                    details={"task_ids": revert_needed},
                )

            for task in tasks:
                if dispositions.get(str(task.task_id)) != "QUIESCE":
                    continue
                await self._quiesce_task(
                    active,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    task=task,
                    runs=runs,
                    attempts=attempt_by_id,
                )

            new_graph_id = uuid7()
            keep = [
                task
                for task in tasks
                if dispositions.get(str(task.task_id)) in {"PRESERVE", "QUIESCE"}
            ]
            moved = [
                item.model_copy(update={"graph_id": new_graph_id}) for item in keep
            ]
            extra = [
                item.model_copy(update={"graph_id": new_graph_id})
                for item in [*replacement_tasks, *revert_tasks]
            ]
            existing_edges = await self._graphs.list_edges_for_graph(
                tenant_id=tenant_id,
                project_id=project_id,
                graph_id=graph_id,
                uow=active,
            )
            keep_ids = {item.task_id for item in moved}
            copied_edges = [
                edge.model_copy(update={"edge_id": uuid7(), "graph_id": new_graph_id})
                for edge in existing_edges
                if edge.from_task_id in keep_ids and edge.to_task_id in keep_ids
            ]
            extra_edges = [
                edge.model_copy(update={"graph_id": new_graph_id})
                for edge in replacement_edges
            ]
            new_graph = await self._graphs.replan_task_graph(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                prior_graph_id=graph_id,
                new_graph_id=new_graph_id,
                keep_tasks=moved,
                new_tasks=extra,
                edges=[*copied_edges, *extra_edges],
                planner_policy_version=PLANNER_POLICY_VERSION,
                created_by_principal=created_by_principal,
                approved_requirement_slugs=approved_requirement_slugs,
                rationale=f"replan:{trigger}",
                uow=active,
            )
            if new_graph.status == "ACTIVE":
                await self._apply_dispositions(
                    active,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    tasks=tasks,
                    dispositions=dispositions,
                    explanations=explanations,
                    new_graph_id=new_graph_id,
                    extra=extra,
                )
                if copied_edges or extra_edges:
                    await self._graphs.create_edges(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        edges=[*copied_edges, *extra_edges],
                        uow=active,
                    )

            decision = ReplanDecision(
                graph_id=graph_id,
                trigger=trigger,
                dispositions=dispositions,
                explanations=explanations,
            )
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ReplanDecided",
                aggregate_type="task_graph",
                aggregate_id=new_graph.graph_id,
                mission_id=mission_id,
                payload={
                    "prior_graph_id": str(graph_id),
                    "new_graph_id": str(new_graph.graph_id),
                    "trigger": trigger,
                    "dispositions": dispositions,
                    "explanations": explanations,
                },
                uow=active,
            )
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result={
                    "decision": decision.model_dump(mode="json"),
                    "graph": new_graph.model_dump(mode="json"),
                },
                uow=active,
            )
            return decision, new_graph

        return await self._run(uow, tenant_id, project_id, _op)

    async def _apply_dispositions(
        self,
        active: PostgresUnitOfWork,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        tasks: Sequence[Task],
        dispositions: Mapping[str, str],
        explanations: Mapping[str, str],
        new_graph_id: UUID,
        extra: Sequence[Task],
    ) -> None:
        for task in tasks:
            key = str(task.task_id)
            disp = dispositions.get(key)
            if task.status in {"SUPERSEDED", "RETIRED"}:
                continue
            if disp in {"SUPERSEDE", "RETIRE"}:
                held = await self._leases.list_held_for_task(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    task_id=task.task_id,
                    uow=active,
                )
                if held:
                    await self._events.append(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        event_type="WriteScopeLeaseHeldAcrossReplan",
                        aggregate_type="task",
                        aggregate_id=task.task_id,
                        mission_id=mission_id,
                        task_id=task.task_id,
                        payload={
                            "disposition": disp,
                            "lease_ids": [str(item.lease_id) for item in held],
                            "reason": (
                                "Chapter 4.6: leases released only after "
                                "workspaces are discarded"
                            ),
                        },
                        uow=active,
                    )
                target = "SUPERSEDED" if disp == "SUPERSEDE" else "RETIRED"
                if task.status not in {"SUPERSEDED", "RETIRED"}:
                    await self._missions.transition_task(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        task_id=task.task_id,
                        target_status=target,
                        lock_version=task.lock_version,
                        uow=active,
                    )
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="ReplanDispositionRecorded",
                    aggregate_type="task",
                    aggregate_id=task.task_id,
                    mission_id=mission_id,
                    task_id=task.task_id,
                    payload={
                        "disposition": disp,
                        "explanation": explanations.get(key, ""),
                    },
                    uow=active,
                )
            elif disp in {"PRESERVE", "QUIESCE"}:
                await self._missions.rebind_task_graph(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    task_id=task.task_id,
                    graph_id=new_graph_id,
                    lock_version=task.lock_version,
                    uow=active,
                )
        for task in extra:
            await self._missions.insert_task(
                tenant_id=tenant_id,
                project_id=project_id,
                task=task,
                uow=active,
            )

    def _node_sets(
        self,
        tasks: Sequence[Task],
        *,
        attempts: Sequence[TaskAttempt],
        runs: Sequence[WorkerRun],
    ) -> tuple[set[UUID], set[UUID], set[UUID]]:
        attempt_by_id = {item.attempt_id: item for item in attempts}
        in_flight: set[UUID] = set()
        completed: set[UUID] = set()
        for attempt in attempts:
            if attempt.status == "COMPLETED":
                completed.add(attempt.task_id)
            elif attempt.status == "IN_PROGRESS":
                in_flight.add(attempt.task_id)
        for run in runs:
            bound = attempt_by_id.get(run.task_attempt_id)
            if bound is None:
                continue
            if run.status not in _TERMINAL_RUNS:
                in_flight.add(bound.task_id)
        integrated = {task.task_id for task in tasks if task.status == "COMPLETED"}
        return in_flight, completed, integrated

    async def _quiesce_task(
        self,
        active: PostgresUnitOfWork,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task: Task,
        runs: Sequence[WorkerRun],
        attempts: dict[UUID, TaskAttempt],
    ) -> Checkpoint | None:
        matching: list[WorkerRun] = []
        for run in runs:
            found = attempts.get(run.task_attempt_id)
            if found is not None and found.task_id == task.task_id:
                matching.append(run)
        if not matching:
            return None
        lead = matching[-1]
        prior = await self._checkpoints.latest_valid_for_task(
            tenant_id=tenant_id,
            project_id=project_id,
            task_id=task.task_id,
            uow=active,
        )
        inherited = list(prior.do_not_repeat) if prior is not None else []
        effects = await self._effects.list_for_run(
            tenant_id=tenant_id,
            project_id=project_id,
            worker_run_id=lead.run_id,
            uow=active,
        )
        tokens = list(dict.fromkeys([*inherited, *do_not_repeat_from_effects(effects)]))
        events = await self._worker_events.list_for_run(active.connection, lead.run_id)
        sequence = events[-1].sequence if events else 0
        return await self._checkpoints.record(
            run=lead,
            task_id=task.task_id,
            workspace_revision=prior.workspace_revision if prior else "",
            event_sequence=sequence,
            completed_work=list(prior.completed_work) if prior else [],
            verified_work=list(prior.verified_work) if prior else [],
            pending_work=[str(task.task_id)],
            known_failures=list(prior.known_failures) if prior else [],
            next_action="resume",
            do_not_repeat=tokens,
            artifact_refs=list(prior.artifact_refs) if prior else [],
            lease_refs=list(prior.lease_refs) if prior else [],
            idempotency_key=f"{lead.run_id}:replan-quiesce",
            uow=active,
        )

    def _tasks_for_effects(
        self,
        effects: Sequence[ExternalEffect],
        *,
        runs: Sequence[WorkerRun],
        attempts: dict[UUID, TaskAttempt],
    ) -> set[UUID]:
        run_by_id = {run.run_id: run for run in runs}
        found: set[UUID] = set()
        for effect in effects:
            run = run_by_id.get(effect.worker_run_id)
            if run is None:
                continue
            attempt = attempts.get(run.task_attempt_id)
            if attempt is None:
                continue
            found.add(attempt.task_id)
        return found

    async def _count_verification_failures(
        self, active: PostgresUnitOfWork, task_id: UUID
    ) -> int:
        rows = await self._verifications.list_for_task(active.connection, task_id)
        return sum(1 for row in rows if row.status == "FAILED")

    def _raise_unless_allowed(self, decision: RecoveryDecision) -> None:
        if decision.allow_new_worker_run:
            return
        raise DdeError(
            decision.error_code,
            decision.message,
            retryable=decision.retryable,
            details={
                "failure_class": decision.failure_class,
                "action": decision.action,
                "requires_replan": decision.requires_replan,
                "matrix_version": decision.matrix_version,
            },
        )
