"""Production Checkpoint writer (Chapter 12.1) -- the sole inserter of
`checkpoints` rows.

A checkpoint is a reconstructible continuation contract. It never replaces
the event history. `do_not_repeat` holds logical mutation scope tokens
(`engine.recovery.hashing.mutation_scope_token`), not caller-chosen
idempotency keys, so a new WorkerRun / new key cannot bypass it.

**Call sites.** `WorkerManagerService.invoke_run` / `resume_run` after a
terminal run; `VerificationRunnerService.run` after a PASSED verdict;
`MissionWorkflowService.checkpoint` / `pause`.

**Deferred.** Partition-detach exemption for worker_events referenced by an
unresolved checkpoint (Chapter 3.7) -- detach itself is not built.
WorkerAdapter.pause/resume for asynchronous harnesses (the certified
scripted profile is synchronous and still returns accepted=False).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.checkpoint import Checkpoint
from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.external_effect import ExternalEffect
from engine.contracts.worker_run import WorkerRun
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.recovery.checkpoint_repository import CheckpointRepository
from engine.recovery.hashing import checkpoint_integrity_hash, mutation_scope_token
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

_CONFIRMED_MUTATION_STATUSES = frozenset({"CONFIRMED"})


def do_not_repeat_from_effects(effects: Sequence[ExternalEffect]) -> list[str]:
    """Load-bearing Chapter 12.1 list: mutations whose durable result is
    present. UNKNOWN/SENT/RECONCILING are omitted -- those must reconcile
    (Chapter 12.4), not be skipped.
    """
    tokens: list[str] = []
    seen: set[str] = set()
    for effect in effects:
        present = effect.status in _CONFIRMED_MUTATION_STATUSES or (
            effect.status == "RECONCILED" and effect.confirmed_at is not None
        )
        if not present:
            continue
        token = mutation_scope_token(
            target_system=effect.target_system,
            target_resource=effect.target_resource,
            operation=effect.operation,
        )
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def continuation_payload(
    *,
    task_id: UUID,
    task_attempt_id: UUID,
    worker_run_id: UUID,
    context_package_id: UUID,
    execution_plan_id: UUID,
    completed_work: list[str],
    verified_work: list[str],
    pending_work: list[str],
    known_failures: list[str],
    next_action: str,
    do_not_repeat: list[str],
    artifact_refs: list[UUID],
    lease_refs: list[UUID],
    workspace_revision: str,
    integration_state: str,
    event_sequence: int,
) -> dict[str, object]:
    return {
        "task_id": str(task_id),
        "task_attempt_id": str(task_attempt_id),
        "worker_run_id": str(worker_run_id),
        "context_package_id": str(context_package_id),
        "execution_plan_id": str(execution_plan_id),
        "completed_work": completed_work,
        "verified_work": verified_work,
        "pending_work": pending_work,
        "known_failures": known_failures,
        "next_action": next_action,
        "do_not_repeat": do_not_repeat,
        "artifact_refs": [str(item) for item in artifact_refs],
        "lease_refs": [str(item) for item in lease_refs],
        "workspace_revision": workspace_revision,
        "integration_state": integration_state,
        "event_sequence": event_sequence,
    }


class CheckpointService:
    """Append-only PostgreSQL writer for Chapter 12.1 checkpoints."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: CheckpointRepository | None = None,
        events: EventService | None = None,
        commands: CommandLedger | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or CheckpointRepository()
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
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

    async def record(
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
        integration_state: str = "",
        uow: PostgresUnitOfWork | None = None,
    ) -> Checkpoint:
        """Insert one append-only snapshot of the run's continuation."""
        if next_action.strip() == "":
            raise DdeError("POLICY_DENIED", "Checkpoint next_action must not be empty")
        payload = continuation_payload(
            task_id=task_id,
            task_attempt_id=run.task_attempt_id,
            worker_run_id=run.run_id,
            context_package_id=run.context_package_id,
            execution_plan_id=run.execution_plan_id,
            completed_work=completed_work,
            verified_work=verified_work,
            pending_work=pending_work,
            known_failures=known_failures,
            next_action=next_action,
            do_not_repeat=do_not_repeat,
            artifact_refs=artifact_refs,
            lease_refs=lease_refs,
            workspace_revision=workspace_revision,
            integration_state=integration_state,
            event_sequence=event_sequence,
        )
        digest = checkpoint_integrity_hash(payload)

        async def _op(active: PostgresUnitOfWork) -> Checkpoint:
            record, is_new = await self._commands.begin(
                tenant_id=run.tenant_id,
                project_id=run.project_id,
                idempotency_key=idempotency_key,
                request_hash=digest,
                uow=active,
            )
            if not is_new:
                return self._replay_or_raise(record)

            now = self._clock.now()
            checkpoint = Checkpoint(
                checkpoint_id=uuid7(),
                tenant_id=run.tenant_id,
                project_id=run.project_id,
                mission_id=run.mission_id,
                task_id=task_id,
                task_attempt_id=run.task_attempt_id,
                worker_run_id=run.run_id,
                context_package_id=run.context_package_id,
                execution_plan_id=run.execution_plan_id,
                completed_work=completed_work,
                verified_work=verified_work,
                pending_work=pending_work,
                known_failures=known_failures,
                next_action=next_action,
                do_not_repeat=do_not_repeat,
                artifact_refs=artifact_refs,
                lease_refs=lease_refs,
                workspace_revision=workspace_revision,
                integration_state=integration_state,
                event_sequence=event_sequence,
                integrity_hash=digest,
                command_id=record.command_id,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_checkpoint(active.connection, checkpoint)
            await self._events.append(
                tenant_id=run.tenant_id,
                project_id=run.project_id,
                event_type="CheckpointRecorded",
                aggregate_type="checkpoint",
                aggregate_id=checkpoint.checkpoint_id,
                mission_id=run.mission_id,
                task_id=task_id,
                payload={
                    "worker_run_id": str(run.run_id),
                    "task_attempt_id": str(run.task_attempt_id),
                    "next_action": next_action,
                    "do_not_repeat": do_not_repeat,
                },
                uow=active,
            )
            await self._commands.complete(
                tenant_id=run.tenant_id,
                project_id=run.project_id,
                command_id=record.command_id,
                result=checkpoint.model_dump(mode="json"),
                uow=active,
            )
            return checkpoint

        return await self._run(uow, run.tenant_id, run.project_id, _op)

    async def get_checkpoint(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        checkpoint_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> Checkpoint:
        async def _op(active: PostgresUnitOfWork) -> Checkpoint:
            record = await self._repository.get_by_id(active.connection, checkpoint_id)
            if record is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "Unknown checkpoint",
                    details={"checkpoint_id": str(checkpoint_id)},
                )
            return record

        return await self._run(uow, tenant_id, project_id, _op)

    async def latest_valid_for_task(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> Checkpoint | None:
        """Newest checkpoint whose integrity_hash still matches. Invalid
        rows are skipped, never silently used.
        """

        async def _op(active: PostgresUnitOfWork) -> Checkpoint | None:
            rows = await self._repository.list_for_task(active.connection, task_id)
            for item in rows:
                if self.is_valid(item):
                    return item
            return None

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_for_mission(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[Checkpoint]:
        async def _op(active: PostgresUnitOfWork) -> list[Checkpoint]:
            return await self._repository.list_for_mission(
                active.connection, mission_id
            )

        return await self._run(uow, tenant_id, project_id, _op)

    def is_valid(self, checkpoint: Checkpoint) -> bool:
        expected = checkpoint_integrity_hash(
            continuation_payload(
                task_id=checkpoint.task_id,
                task_attempt_id=checkpoint.task_attempt_id,
                worker_run_id=checkpoint.worker_run_id,
                context_package_id=checkpoint.context_package_id,
                execution_plan_id=checkpoint.execution_plan_id,
                completed_work=checkpoint.completed_work,
                verified_work=checkpoint.verified_work,
                pending_work=checkpoint.pending_work,
                known_failures=checkpoint.known_failures,
                next_action=checkpoint.next_action,
                do_not_repeat=checkpoint.do_not_repeat,
                artifact_refs=checkpoint.artifact_refs,
                lease_refs=checkpoint.lease_refs,
                workspace_revision=checkpoint.workspace_revision,
                integration_state=checkpoint.integration_state,
                event_sequence=checkpoint.event_sequence,
            )
        )
        return expected == checkpoint.integrity_hash

    def _replay_or_raise(self, record: CommandIdempotency) -> Checkpoint:
        if record.status == "completed" and record.result is not None:
            return Checkpoint.model_validate(record.result)
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
