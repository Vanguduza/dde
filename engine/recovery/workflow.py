"""Chapter 12.6 MissionWorkflow -- backend-neutral interface over
PostgreSQL state (v1). Redis remains the outbox transport; this module
does not introduce a durable workflow engine (that would be an EDR).

Implemented production methods: `checkpoint`, `resume`, `pause` (checkpoint
then mission PAUSED, inheriting prior `do_not_repeat`), `retry` (Chapter
12.3 matrix; generic retry without a failure class is refused), `reroute`
(returns a ROUTING_FAILURE decision; does not invent a RouteDecision),
`request_approval` (Chapter 13.1/13.3: durable Approval, BLOCKED_ON_DECISION,
mission PARTIAL).

Deferred (raise POLICY_DENIED, do not pretend): `wait`. Automatic insertion
of a new `decision` TaskGraph node on every request is deferred when the
graph already models `blocks_on_decision` (Chapter 4.11 fixture); callers
add a node via `MissionService.amend_task_graph(add_task)` which is
auto-accepted. `start` / `cancel` / `complete` / `fail` stay on
`MissionService` -- wrapping them here would overclaim ownership of the
mission kernel.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.approval import Approval
from engine.contracts.checkpoint import Checkpoint
from engine.contracts.mission import Mission
from engine.contracts.worker_run import WorkerRun
from engine.core.errors import DdeError
from engine.events.service import EventService
from engine.governance.hashing import approval_scope_hash
from engine.governance.service import ApprovalService
from engine.missions.attempts import TaskAttemptService
from engine.missions.service import MissionService
from engine.recovery.checkpoint_service import CheckpointService
from engine.recovery.dispatch import RecoveryService
from engine.recovery.matrix import RecoveryDecision, decide
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

    async def retry(self, *, policy: dict[str, object]) -> RecoveryDecision: ...

    async def wait(self, *, condition: str) -> None: ...

    async def request_approval(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        approval_type: str,
        requested_by: UUID,
        idempotency_key: str,
        reason: str,
        task_id: UUID | None = None,
        payload: dict[str, object] | None = None,
    ) -> Approval: ...

    async def reroute(self, *, reason: str) -> RecoveryDecision: ...


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
        recovery: RecoveryService | None = None,
        approvals: ApprovalService | None = None,
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
        self._recovery = recovery or RecoveryService(
            engine,
            events=self._events,
            checkpoints=self._checkpoints,
            attempts=self._attempts,
            missions=self._missions,
        )
        self._approvals = approvals or ApprovalService(engine, events=self._events)

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
                prior = await self._checkpoints.latest_valid_for_task(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    task_id=attempt.task_id,
                    uow=active,
                )
                inherited = list(prior.do_not_repeat) if prior is not None else []
                await self._checkpoints.record(
                    run=lead,
                    task_id=attempt.task_id,
                    workspace_revision=attempt.workspace_revision,
                    event_sequence=sequence,
                    completed_work=list(prior.completed_work) if prior else [],
                    verified_work=list(prior.verified_work) if prior else [],
                    pending_work=[str(attempt.task_id)],
                    known_failures=list(prior.known_failures) if prior else [],
                    next_action="resume",
                    do_not_repeat=inherited,
                    artifact_refs=list(prior.artifact_refs) if prior else [],
                    lease_refs=list(prior.lease_refs) if prior else [],
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

    async def retry(self, *, policy: dict[str, object]) -> RecoveryDecision:
        failure_class = policy.get("failure_class")
        if not isinstance(failure_class, str) or failure_class.strip() == "":
            raise DdeError(
                "POLICY_DENIED",
                "recovery dispatches on failure class, never on a generic retry",
                retryable=False,
                details={"policy": policy},
            )
        raw_count = policy.get("occurrence_count", 1)
        count = raw_count if isinstance(raw_count, int) else 1
        decision = self._recovery.decision_for_policy(
            failure_class=failure_class, occurrence_count=count
        )
        if not decision.allow_new_worker_run:
            raise DdeError(
                decision.error_code,
                decision.message,
                retryable=decision.retryable,
                details={
                    "failure_class": decision.failure_class,
                    "action": decision.action,
                    "requires_replan": decision.requires_replan,
                },
            )
        return decision

    async def wait(self, *, condition: str) -> None:
        raise DdeError(
            "POLICY_DENIED",
            "MissionWorkflow.wait is not built (no condition scheduler)",
            retryable=False,
            details={"condition": condition},
        )

    async def request_approval(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        approval_type: str,
        requested_by: UUID,
        idempotency_key: str,
        reason: str,
        task_id: UUID | None = None,
        payload: dict[str, object] | None = None,
    ) -> Approval:
        """Chapter 13.3: persist an Approval, block only the named task,
        and move the mission to PARTIAL so independent branches continue.
        """
        if reason.strip() == "":
            raise DdeError(
                "POLICY_DENIED",
                "request_approval requires a reason",
                retryable=False,
            )

        async def _op(active: PostgresUnitOfWork) -> Approval:
            mission = await self._missions.get_mission(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                uow=active,
            )
            scope = approval_scope_hash(
                approval_type=approval_type,
                mission_id=mission_id,
                task_id=task_id,
                payload=payload or {"reason": reason},
            )
            approval = await self._approvals.request(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                approval_type=approval_type,
                scope_hash=scope,
                requested_by=requested_by,
                idempotency_key=idempotency_key,
                task_id=task_id,
                suggested_decision=reason,
                uow=active,
            )
            if task_id is not None:
                task = await self._missions.get_task(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    task_id=task_id,
                    uow=active,
                )
                await self._missions.transition_task(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    task_id=task_id,
                    target_status="BLOCKED_ON_DECISION",
                    lock_version=task.lock_version,
                    uow=active,
                )
            if mission.status == "ACTIVE":
                await self._missions.transition_mission(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=mission_id,
                    target_status="PARTIAL",
                    lock_version=mission.lock_version,
                    uow=active,
                )
            return approval

        return await self._run(None, tenant_id, project_id, _op)

    async def expire_and_park(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission: Mission,
        approval_id: UUID,
    ) -> Mission:
        """Chapter 13.3.4: expiry parks the mission (not failure)."""

        async def _op(active: PostgresUnitOfWork) -> Mission:
            await self._approvals.expire(
                tenant_id=tenant_id,
                project_id=project_id,
                approval_id=approval_id,
                uow=active,
            )
            current = await self._missions.get_mission(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission.mission_id,
                uow=active,
            )
            if current.status in {"ACTIVE", "PARTIAL"}:
                return await self.pause(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission=current,
                    uow=active,
                )
            return current

        return await self._run(None, tenant_id, project_id, _op)

    async def reroute(self, *, reason: str) -> RecoveryDecision:
        decision = decide("ROUTING_FAILURE", occurrence_count=1)
        if reason.strip() == "":
            raise DdeError(
                "POLICY_DENIED",
                "MissionWorkflow.reroute requires a reason",
                retryable=False,
            )
        return decision
