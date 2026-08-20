"""Chapter 12.5 replay planner -- reconstruct next legal work from the
latest valid checkpoint plus durable TaskAttempt results.

Replay never re-runs a COMPLETED attempt because a later task failed.
Replay never repeats a mutation listed in checkpoint.do_not_repeat.
If the checkpoint is older than the hot event window (Chapter 3.7, 90
days), the result sets event_window_expired and reconstructs from
checkpoint plus attempts only -- it never silently uses a partial event
stream. Callers that required events raise EVENT_WINDOW_EXPIRED via
`ReplayPlan.require_events()`.

**Not this mission.** Failure-class dispatch / replan (Chapter 12.3,
DDE-024). Partition detach of old `events`/`worker_events` (Chapter 3.7
archival) -- the window check is still enforced against checkpoint age.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.checkpoint import Checkpoint
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.missions.attempts import TaskAttemptService
from engine.recovery.checkpoint_service import CheckpointService
from engine.recovery.hashing import mutation_scope_token
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

#: Chapter 3.7 default hot window for worker_events. Expiring a
#: reconstruction earlier would force checkpoint fallback; later would
#: pretend detached history is still readable.
WORKER_EVENT_HOT_WINDOW = timedelta(days=90)

EVENT_WINDOW_EXPIRED = "EVENT_WINDOW_EXPIRED"
ATTEMPT_COMPLETED = "ATTEMPT_COMPLETED"
MUTATION_ALREADY_DONE = "MUTATION_ALREADY_DONE"


@dataclass(frozen=True)
class ReplayPlan:
    """Internal continuation plan (AGENTS.md: dataclass, not a contract)."""

    mission_id: UUID
    checkpoint: Checkpoint | None
    skip_task_ids: tuple[UUID, ...]
    resume_attempt_ids: tuple[UUID, ...]
    next_action: str
    reconstruction_source: Literal["events", "checkpoint_and_attempts"]
    event_window_expired: bool
    do_not_repeat: tuple[str, ...]

    def require_events(self) -> None:
        """Chapter 3.7: a caller that needed the hot event window must
        observe EVENT_WINDOW_EXPIRED rather than a silent fallback.
        """
        if self.event_window_expired:
            raise DdeError(
                EVENT_WINDOW_EXPIRED,
                "Replay required detached event history; recovering from "
                "checkpoint plus durable attempt results instead",
                retryable=False,
                details={
                    "mission_id": str(self.mission_id),
                    "reconstruction_source": self.reconstruction_source,
                    "checkpoint_id": (
                        str(self.checkpoint.checkpoint_id)
                        if self.checkpoint is not None
                        else None
                    ),
                },
            )


class ReplayService:
    """Read-side planner plus the mutation gates invoke_run must call."""

    def __init__(
        self,
        engine: AsyncEngine,
        checkpoints: CheckpointService | None = None,
        attempts: TaskAttemptService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._checkpoints = checkpoints or CheckpointService(engine)
        self._attempts = attempts or TaskAttemptService(engine)
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

    async def plan_for_mission(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> ReplayPlan:
        async def _op(active: PostgresUnitOfWork) -> ReplayPlan:
            attempts = await self._attempts.list_for_mission(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                uow=active,
            )
            skip: list[UUID] = []
            resume: list[UUID] = []
            seen_completed: set[UUID] = set()
            for attempt in attempts:
                if attempt.status == "COMPLETED":
                    seen_completed.add(attempt.task_id)
                    skip.append(attempt.task_id)
                elif (
                    attempt.status == "IN_PROGRESS"
                    and attempt.task_id not in seen_completed
                ):
                    resume.append(attempt.attempt_id)
            checkpoints = await self._checkpoints.list_for_mission(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                uow=active,
            )
            latest_valid: Checkpoint | None = None
            for item in reversed(checkpoints):
                if self._checkpoints.is_valid(item):
                    latest_valid = item
                    break
            expired = self._window_expired(latest_valid)
            source: Literal["events", "checkpoint_and_attempts"] = (
                "checkpoint_and_attempts" if expired else "events"
            )
            do_not_repeat = tuple(latest_valid.do_not_repeat) if latest_valid else ()
            next_action = (
                latest_valid.next_action
                if latest_valid is not None
                else ("resume" if resume else "complete")
            )
            return ReplayPlan(
                mission_id=mission_id,
                checkpoint=latest_valid,
                skip_task_ids=tuple(dict.fromkeys(skip)),
                resume_attempt_ids=tuple(resume),
                next_action=next_action,
                reconstruction_source=source,
                event_window_expired=expired,
                do_not_repeat=do_not_repeat,
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def assert_clear_to_start_attempt(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID,
        target_system: str,
        target_resource: str,
        operation: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> None:
        """Refuse a new TaskAttempt/WorkerRun that would re-run completed
        sibling work or a do_not_repeat mutation. Called from
        `WorkerManagerService.invoke_run` before insert.
        """

        async def _op(active: PostgresUnitOfWork) -> None:
            existing = await self._attempts.list_for_task(
                tenant_id=tenant_id,
                project_id=project_id,
                task_id=task_id,
                uow=active,
            )
            completed = [row for row in existing if row.status == "COMPLETED"]
            if completed:
                lead = completed[0]
                raise DdeError(
                    ATTEMPT_COMPLETED,
                    "Refusing to re-run a completed TaskAttempt because a "
                    "later task failed or a new invocation arrived "
                    f"(attempt_id={lead.attempt_id})",
                    retryable=False,
                    details={
                        "task_id": str(task_id),
                        "attempt_id": str(lead.attempt_id),
                    },
                )
            checkpoint = await self._checkpoints.latest_valid_for_task(
                tenant_id=tenant_id,
                project_id=project_id,
                task_id=task_id,
                uow=active,
            )
            if checkpoint is None:
                return
            token = mutation_scope_token(
                target_system=target_system,
                target_resource=target_resource,
                operation=operation,
            )
            if token in checkpoint.do_not_repeat:
                raise DdeError(
                    MUTATION_ALREADY_DONE,
                    "Refusing to repeat a mutation listed in "
                    "checkpoint.do_not_repeat "
                    f"(checkpoint_id={checkpoint.checkpoint_id})",
                    retryable=False,
                    details={
                        "checkpoint_id": str(checkpoint.checkpoint_id),
                        "token": token,
                    },
                )

        await self._run(uow, tenant_id, project_id, _op)

    def _window_expired(self, checkpoint: Checkpoint | None) -> bool:
        if checkpoint is None:
            return False
        cutoff = self._clock.now() - WORKER_EVENT_HOT_WINDOW
        return checkpoint.created_at <= cutoff
