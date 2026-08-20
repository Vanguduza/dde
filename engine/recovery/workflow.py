"""Chapter 12.6 MissionWorkflow -- backend-neutral interface over
PostgreSQL state (v1). Redis remains the outbox transport; this module
does not introduce a durable workflow engine (that would be an EDR).

Implemented production methods: `checkpoint`, `resume`, `pause` (checkpoint
then mission PAUSED), `retry` (refuses a generic retry; the Chapter 12.3
matrix is DDE-024).

Deferred (raise POLICY_DENIED, do not pretend): `wait`, `request_approval`
(DDE-026), `reroute` (DDE-024). `start` / `cancel` / `complete` / `fail`
stay on `MissionService` -- wrapping them here would overclaim ownership
of the mission kernel.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.checkpoint import Checkpoint
from engine.contracts.mission import Mission
from engine.contracts.worker_run import WorkerRun
from engine.core.errors import DdeError
from engine.events.service import EventService
from engine.missions.attempts import TaskAttemptService
from engine.missions.service import MissionService
from engine.recovery.checkpoint_service import CheckpointService
from engine.recovery.replay import ReplayPlan, ReplayService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.workers.repository import WorkerEventRepository, WorkerRunRepository

T = TypeVar("T")


class MissionWorkflow(Protocol):
    """Chapter 12.6 method names, verbatim."""

    async def checkpoint(
        self,
        *,
        run: WorkerRun,
        task_id: UUID,
        workspace_revision: str,
        event_sequence: int,
        completed_work: list[str],
        verified_work: list[str],
        pending_work: list[str],
        known_failures: list[str],
        next_action: str,
        do_not_repeat: list[str],
        artifact_refs: list[UUID],
        lease_refs: list[UUID],
        idempotency_key: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> Checkpoint: ...

    async def resume(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> ReplayPlan: ...

    async def pause(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission: Mission,
        uow: PostgresUnitOfWork | None = None,
    ) -> Mission: ...

    async def retry(self, *, policy: dict[str, object]) -> None: ...

    async def wait(self, *, condition: str) -> None: ...

    async def request_approval(self, *, reason: str) -> None: ...

    async def reroute(self, *, reason: str) -> None: ...


class MissionWorkflowService:
    """PostgreSQL v1 MissionWorkflow (Chapter 12.6)."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        checkpoints: CheckpointService | None = None,
        replay: ReplayService | None = None,
        missions: MissionService | None = None,
        attempts: TaskAttemptService | None = None,
        runs: WorkerRunRepository | None = None,
        worker_events: WorkerEventRepository | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._checkpoints = checkpoints or CheckpointService(
            engine, events=self._events
        )
        self._attempts = attempts or TaskAttemptService(engine, events=self._events)
        self._replay = replay or ReplayService(
            engine, checkpoints=self._checkpoints, attempts=self._attempts
        )
        self._missions = missions or MissionService(engine, events=self._events)
        self._runs = runs or WorkerRunRepository()
        self._worker_events = worker_events or WorkerEventRepository()

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

    async def checkpoint(
        self,
        *,
        run: WorkerRun,
        task_id: UUID,
        workspace_revision: str,
        event_sequence: int,
        completed_work: list[str],
        verified_work: list[str],
        pending_work: list[str],
        known_failures: list[str],
        next_action: str,
        do_not_repeat: list[str],
        artifact_refs: list[UUID],
        lease_refs: list[UUID],
        idempotency_key: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> Checkpoint:
        return await self._checkpoints.record(
            run=run,
            task_id=task_id,
            workspace_revision=workspace_revision,
            event_sequence=event_sequence,
            completed_work=completed_work,
            verified_work=verified_work,
            pending_work=pending_work,
            known_failures=known_failures,
            next_action=next_action,
            do_not_repeat=do_not_repeat,
            artifact_refs=artifact_refs,
            lease_refs=lease_refs,
            idempotency_key=idempotency_key,
            uow=uow,
        )

    async def resume(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> ReplayPlan:
        """Reconstruct from latest valid checkpoint plus durable completed
        attempts. When the hot event window has expired the plan still
        contains that reconstruction and `event_window_expired` is set;
        callers that needed events must call `ReplayPlan.require_events()`.
        This method does not dispatch a worker.
        """
        return await self._replay.plan_for_mission(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            uow=uow,
        )

    async def pause(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission: Mission,
        uow: PostgresUnitOfWork | None = None,
    ) -> Mission:
        """Park the mission (ACTIVE/PARTIAL -> PAUSED). A checkpoint is
        recorded only when a WorkerRun already exists to snapshot --
        Chapter 12.1 requires worker_run_id.
        """

        async def _op(active: PostgresUnitOfWork) -> Mission:
            runs = await self._runs.list_for_mission(
                active.connection, mission.mission_id
            )
            if runs:
                lead = runs[-1]
                attempt = await self._attempts.get_attempt(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    attempt_id=lead.task_attempt_id,
                    uow=active,
                )
                worker_events = await self._worker_events.list_for_run(
                    active.connection, lead.run_id
                )
                sequence = worker_events[-1].sequence if worker_events else 0
                await self._checkpoints.record(
                    run=lead,
                    task_id=attempt.task_id,
                    workspace_revision=attempt.workspace_revision,
                    event_sequence=sequence,
                    completed_work=[],
                    verified_work=[],
                    pending_work=[str(attempt.task_id)],
                    known_failures=[],
                    next_action="resume",
                    do_not_repeat=[],
                    artifact_refs=[],
                    lease_refs=[],
                    idempotency_key=f"{lead.run_id}:workflow-pause",
                    uow=active,
                )
            return await self._missions.transition_mission(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission.mission_id,
                target_status="PAUSED",
                lock_version=mission.lock_version,
                uow=active,
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def retry(self, *, policy: dict[str, object]) -> None:
        failure_class = policy.get("failure_class")
        if not isinstance(failure_class, str) or failure_class.strip() == "":
            raise DdeError(
                "POLICY_DENIED",
                "recovery dispatches on failure class, never on a generic retry",
                retryable=False,
                details={"policy": policy},
            )
        raise DdeError(
            "POLICY_DENIED",
            "failure-class recovery matrix is DDE-024; refusing to invent a retry",
            retryable=False,
            details={"failure_class": failure_class},
        )

    async def wait(self, *, condition: str) -> None:
        raise DdeError(
            "POLICY_DENIED",
            "MissionWorkflow.wait is not built (no condition scheduler)",
            retryable=False,
            details={"condition": condition},
        )

    async def request_approval(self, *, reason: str) -> None:
        raise DdeError(
            "POLICY_DENIED",
            "MissionWorkflow.request_approval is DDE-026",
            retryable=False,
            details={"reason": reason},
        )

    async def reroute(self, *, reason: str) -> None:
        raise DdeError(
            "POLICY_DENIED",
            "MissionWorkflow.reroute is DDE-024",
            retryable=False,
            details={"reason": reason},
        )
