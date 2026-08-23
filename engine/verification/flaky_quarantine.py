"""Flaky-check quarantine (adoption #7).

REV_2_0 Ch.11.8: "a flaky test is a defect, tracked and repaired, never
retried into green." A check ref whose verdict alternates PASSED/FAILED
across a task's terminal ``VerificationRun``s -- without any code delta
between them -- is not measuring the product. This module owns that
machinery:

- :func:`detect_flaky_checks` -- pure detection over a task's ordered
  ``VerificationRun`` history (``list_for_task`` order, oldest-first): a
  check ref is flaky once its recorded check results contain both PASSED
  and FAILED across terminal runs. ERRORED/PARTIAL runs prove nothing in
  either direction and never feed the verdict.
- :class:`FlakyQuarantineService` -- the durable marker
  (``flaky_quarantines``, migration 0010) plus the two-tier cadence:
  while an ACTIVE quarantine exists AND :func:`reentry_decision` says
  "wait", that check's failure does not escalate recovery; on re-entry
  the plain VERIFICATION_FAILURE row applies again. Quarantine never
  deletes anything: rows keep their sample size, history accumulates,
  and only :meth:`FlakyQuarantineService.lift` deactivates a marker.

Wiring point for governance-approved lift: no approval-shaped call in
``engine.governance`` was reachable without cross-territory edits, so
:meth:`lift` is the single mutation site such wiring would call once an
operator approves a "lift flaky quarantine" attention item.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.contracts.task import Task
from engine.contracts.verification_run import VerificationRun
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.verification.tables import flaky_quarantines

#: A single anomalous run can never quarantine a check: both verdicts
#: must exist across at least this many terminal runs.
DEFAULT_FLAKY_MIN_TERMINAL_RUNS: Final[int] = 2

#: Two-tier cadence defaults: a quarantined check re-enters blocking
#: verification on every Nth run ...
DEFAULT_CADENCE_EVERY_N_RUNS: Final[int] = 5
#: ... or once this many seconds have elapsed since detection, whichever
#: comes first. Both knobs are mechanical and injectable.
DEFAULT_CADENCE_INTERVAL_SECONDS: Final[int] = 3600

TERMINAL_RUN_STATUSES: Final[frozenset[str]] = frozenset({"PASSED", "FAILED"})


@dataclass(frozen=True)
class CadencePolicy:
    """Two-tier cadence knobs."""

    every_n_runs: int = DEFAULT_CADENCE_EVERY_N_RUNS
    interval_seconds: int = DEFAULT_CADENCE_INTERVAL_SECONDS


@dataclass(frozen=True)
class ReentryDecision:
    """Mechanical answer to 'does this quarantined check block now?'"""

    reentered: bool
    reason: str


def detect_flaky_checks(
    runs: list[VerificationRun],
    *,
    min_terminal_runs: int = DEFAULT_FLAKY_MIN_TERMINAL_RUNS,
) -> frozenset[str]:
    """Check refs whose verdict alternated across terminal runs.

    ``runs`` must be oldest-first (``list_for_task`` order). Only PASSED
    and FAILED runs carry verdicts; ERRORED/PARTIAL prove nothing in
    either direction and never feed a flaky verdict.
    """
    statuses: dict[str, set[str]] = defaultdict(set)
    for run in runs:
        if run.status not in TERMINAL_RUN_STATUSES:
            continue
        for result in run.check_results:
            statuses[result.check_ref].add(result.status)
    return frozenset(
        check_ref
        for check_ref, verdicts in statuses.items()
        if len(verdicts & TERMINAL_RUN_STATUSES) == 2
        and len(verdicts) >= min_terminal_runs
    )


def reentry_decision(
    *,
    detected_at: datetime,
    now: datetime,
    terminal_runs_since: int,
    cadence: CadencePolicy,
) -> ReentryDecision:
    """Pure Nth-run / time-based cadence evaluation.

    Re-enter blocking verification when the interval elapsed or the run
    count since detection hits a multiple of ``every_n_runs`` -- interval
    first, then Nth-run. Zero elapsed time and zero runs means wait.
    """
    if (
        cadence.interval_seconds > 0
        and (now - detected_at).total_seconds() >= cadence.interval_seconds
    ):
        return ReentryDecision(True, "interval_elapsed")
    if (
        cadence.every_n_runs > 0
        and terminal_runs_since > 0
        and terminal_runs_since % cadence.every_n_runs == 0
    ):
        return ReentryDecision(True, f"nth_run:{terminal_runs_since}")
    return ReentryDecision(False, "cadence_wait")


@dataclass(frozen=True)
class FlakyQuarantineRecord:
    """One durable quarantine marker row."""

    quarantine_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    check_ref: str
    detected_at: datetime
    lifted_at: datetime | None
    lifted_by: str | None
    sample_size: int
    created_at: datetime
    updated_at: datetime

    @property
    def active(self) -> bool:
        return self.lifted_at is None


def _record_from_row(row: object) -> FlakyQuarantineRecord:
    mapping: dict[str, object] = dict(row)  # type: ignore[call-overload]
    return FlakyQuarantineRecord(
        quarantine_id=mapping["quarantine_id"],  # type: ignore[arg-type]
        tenant_id=mapping["tenant_id"],  # type: ignore[arg-type]
        project_id=mapping["project_id"],  # type: ignore[arg-type]
        mission_id=mapping["mission_id"],  # type: ignore[arg-type]
        task_id=mapping["task_id"],  # type: ignore[arg-type]
        check_ref=str(mapping["check_ref"]),
        detected_at=mapping["detected_at"],  # type: ignore[arg-type]
        lifted_at=mapping["lifted_at"],  # type: ignore[arg-type]
        lifted_by=(
            str(mapping["lifted_by"]) if mapping["lifted_by"] is not None else None
        ),
        sample_size=int(mapping["sample_size"]),  # type: ignore[call-overload]
        created_at=mapping["created_at"],  # type: ignore[arg-type]
        updated_at=mapping["updated_at"],  # type: ignore[arg-type]
    )


async def _insert(connection: AsyncConnection, record: FlakyQuarantineRecord) -> None:
    await connection.execute(flaky_quarantines.insert().values(**record.__dict__))


async def _list_active(
    connection: AsyncConnection, task_id: UUID
) -> list[FlakyQuarantineRecord]:
    result = await connection.execute(
        select(flaky_quarantines)
        .where(
            flaky_quarantines.c.task_id == task_id,
            flaky_quarantines.c.lifted_at.is_(None),
        )
        .order_by(flaky_quarantines.c.detected_at.asc())
    )
    return [_record_from_row(row) for row in result.mappings().all()]


async def _get_active(
    connection: AsyncConnection, task_id: UUID, check_ref: str
) -> FlakyQuarantineRecord | None:
    result = await connection.execute(
        select(flaky_quarantines)
        .where(
            flaky_quarantines.c.task_id == task_id,
            flaky_quarantines.c.check_ref == check_ref,
            flaky_quarantines.c.lifted_at.is_(None),
        )
        .order_by(flaky_quarantines.c.detected_at.desc())
    )
    row = result.mappings().first()
    return None if row is None else _record_from_row(row)


T = TypeVar("T")


class FlakyQuarantineService:
    """Async, PostgreSQL-backed writer for ``flaky_quarantines`` rows.
    Each public method opens and commits its own unit of work unless one
    is supplied, matching every sibling service in this codebase."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        clock: Clock | None = None,
        cadence: CadencePolicy | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._clock = clock or SystemClock()
        self._cadence = cadence or CadencePolicy()

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

    async def refresh_quarantines(
        self,
        *,
        task: Task,
        runs: list[VerificationRun],
        uow: PostgresUnitOfWork | None = None,
    ) -> list[FlakyQuarantineRecord]:
        """Detect flaky refs over ``runs`` (oldest-first) and durably mark
        each newly flaky one. Idempotent: an already-active marker for the
        same (task, check_ref) is left untouched, never duplicated."""
        flaky_refs = detect_flaky_checks(runs)
        if not flaky_refs:
            return []

        async def _op(
            active: PostgresUnitOfWork,
        ) -> list[FlakyQuarantineRecord]:
            now = self._clock.now()
            created: list[FlakyQuarantineRecord] = []
            for check_ref in sorted(flaky_refs):
                if await _get_active(active.connection, task.task_id, check_ref):
                    continue
                record = FlakyQuarantineRecord(
                    quarantine_id=uuid7(),
                    tenant_id=task.tenant_id,
                    project_id=task.project_id,
                    mission_id=task.mission_id,
                    task_id=task.task_id,
                    check_ref=check_ref,
                    detected_at=now,
                    lifted_at=None,
                    lifted_by=None,
                    sample_size=len(runs),
                    created_at=now,
                    updated_at=now,
                )
                await _insert(active.connection, record)
                await self._events.append(
                    tenant_id=task.tenant_id,
                    project_id=task.project_id,
                    event_type="FlakyCheckQuarantined",
                    aggregate_type="flaky_quarantine",
                    aggregate_id=record.quarantine_id,
                    mission_id=task.mission_id,
                    task_id=task.task_id,
                    payload={
                        "check_ref": check_ref,
                        "sample_size": len(runs),
                    },
                    uow=active,
                )
                created.append(record)
            return created

        return await self._run(uow, task.tenant_id, task.project_id, _op)

    async def deferred_failure_refs(
        self,
        *,
        task: Task,
        runs: list[VerificationRun],
        failed_check_refs: frozenset[str] | list[str],
        uow: PostgresUnitOfWork | None = None,
    ) -> frozenset[str]:
        """Which of ``failed_check_refs`` are quarantined noise RIGHT NOW.

        A ref defers only while an ACTIVE quarantine exists AND
        :func:`reentry_decision` says wait (tier two not yet due).
        ``runs`` is the task's full oldest-first terminal history
        including the run being judged; the per-ref run count since
        detection is computed from it, keeping the cadence mechanical.
        """
        wanted = frozenset(failed_check_refs)

        async def _op(active: PostgresUnitOfWork) -> frozenset[str]:
            active_rows = await _list_active(active.connection, task.task_id)
            if not active_rows or not wanted:
                return frozenset()
            now = self._clock.now()
            deferred: set[str] = set()
            for row in active_rows:
                if row.check_ref not in wanted:
                    continue
                # Runs are oldest-first; a row detected mid-history counts
                # the terminal runs from its detection point onward.
                since = sum(
                    1
                    for run in runs
                    if run.status in TERMINAL_RUN_STATUSES
                    and run.created_at >= row.detected_at
                )
                decision = reentry_decision(
                    detected_at=row.detected_at,
                    now=now,
                    terminal_runs_since=since,
                    cadence=self._cadence,
                )
                if not decision.reentered:
                    deferred.add(row.check_ref)
            return frozenset(deferred)

        return await self._run(uow, task.tenant_id, task.project_id, _op)

    async def lift(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID,
        check_ref: str,
        lifted_by: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> FlakyQuarantineRecord:
        """Operator-driven lift of an active quarantine.

        Governance wiring point: once ``engine.governance``'s
        approval-decision handler is allowed to reach this module, an
        approved "lift flaky quarantine" attention item should call this
        method with the approving principal as ``lifted_by``. Until that
        cross-territory wiring lands, this is the only mutation that
        deactivates a marker."""

        async def _op(active: PostgresUnitOfWork) -> FlakyQuarantineRecord:
            row = await _get_active(active.connection, task_id, check_ref)
            if row is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "no active flaky quarantine for this task/check_ref",
                    details={"check_ref": check_ref},
                )
            now = self._clock.now()
            lifted = FlakyQuarantineRecord(
                **{
                    **row.__dict__,
                    "lifted_at": now,
                    "lifted_by": lifted_by,
                    "updated_at": now,
                }
            )
            await active.connection.execute(
                flaky_quarantines.update()
                .where(
                    flaky_quarantines.c.quarantine_id == row.quarantine_id,
                    flaky_quarantines.c.lifted_at.is_(None),
                )
                .values(lifted_at=now, lifted_by=lifted_by, updated_at=now)
            )
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="FlakyQuarantineLifted",
                aggregate_type="flaky_quarantine",
                aggregate_id=row.quarantine_id,
                task_id=task_id,
                payload={"check_ref": check_ref, "lifted_by": lifted_by},
                uow=active,
            )
            return lifted

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_active(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[FlakyQuarantineRecord]:
        async def _op(active: PostgresUnitOfWork) -> list[FlakyQuarantineRecord]:
            return await _list_active(active.connection, task_id)

        result = await self._run(uow, tenant_id, project_id, _op)
        return list(result)
