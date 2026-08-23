"""Flaky-check quarantine (adoption #7) -- pure detection and cadence
thresholds, plus the durable marker lifecycle against real PostgreSQL
(`flaky_quarantines`, migration 0010).

Pure tests pin: both-verdicts-required detection, ERRORED/PARTIAL runs
proving nothing, the min_terminal_runs floor, interval-first/Nth-run
cadence evaluation. The PostgreSQL suite pins the production mutation
sites: refresh_quarantines' idempotent insert + event, deferred_failure_refs'
two-tier gate against reentry_decision, lift's single deactivation path,
and Chapter 3.2's fail-closed RLS on the new table through a non-superuser
probe role.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from engine.contracts.task import Task
from engine.contracts.verification_run import CheckResult, VerificationRun
from engine.core.ids import uuid7
from engine.truth.db import open_unit_of_work
from engine.verification.flaky_quarantine import (
    CadencePolicy,
    FlakyQuarantineService,
    detect_flaky_checks,
    reentry_decision,
)
from tests.support.db import (
    TenantFixture,
    ensure_rls_probe_role,
    new_engine,
    open_rls_probe,
    seed_tenant,
)

DETECTED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _task(tenant: TenantFixture) -> Task:
    now = datetime.now(UTC)
    return Task.model_validate(
        {
            "task_id": uuid7(),
            "tenant_id": tenant.tenant_id,
            "project_id": tenant.project_id,
            "mission_id": uuid7(),
            "graph_id": uuid7(),
            "title": "t",
            "intent": "i",
            "task_class": "implementation",
            "requirement_refs": ["REQ-1"],
            "feature_refs": [],
            "success_criteria": ["c"],
            "expected_write_scope": ["engine/routing"],
            "expected_read_scope": [],
            "blast_radius": "local",
            "risk_class": "low",
            "estimated_effort": "s",
            "autonomy_ceiling": 2,
            "requires_approval": False,
            "status": "CREATED",
            "lock_version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )


def _check(check_ref: str, status: str) -> CheckResult:
    return CheckResult(
        check_ref=check_ref,
        kind="test",
        command=["pytest", check_ref],
        exit_code=0 if status == "PASSED" else 1,
        stdout="",
        stderr="",
        duration_ms=10,
        timed_out=False,
        status=status,
    )


def _run(
    *,
    check_statuses: dict[str, str],
    run_status: str = "PASSED",
    offset_seconds: int = 0,
) -> VerificationRun:
    moment = DETECTED_AT + timedelta(seconds=offset_seconds)
    return VerificationRun(
        verification_run_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        mission_id=uuid7(),
        task_id=uuid7(),
        task_attempt_id=uuid7(),
        worker_run_id=uuid7(),
        workspace_id=uuid7(),
        oracle_id=uuid7(),
        sequence=offset_seconds,
        status=run_status,
        confidence=0.0,
        check_results=[_check(ref, status) for ref, status in check_statuses.items()],
        outcome_results=[],
        negative_case_results=[],
        evidence_refs=[],
        started_at=moment,
        ended_at=moment,
        created_at=moment,
        updated_at=moment,
    )


# --- detect_flaky_checks ---------------------------------------------------


def test_alternating_verdicts_across_terminal_runs_are_flaky() -> None:
    runs = [
        _run(check_statuses={"tests/a.py::t": "PASSED"}),
        _run(
            check_statuses={"tests/a.py::t": "FAILED"},
            run_status="FAILED",
            offset_seconds=60,
        ),
    ]
    assert detect_flaky_checks(runs) == frozenset({"tests/a.py::t"})


def test_consistent_verdicts_are_never_flaky() -> None:
    always_pass = [_run(check_statuses={"c": "PASSED"})] * 4
    always_fail = [_run(check_statuses={"c": "FAILED"}, run_status="FAILED")] * 3
    assert detect_flaky_checks(always_pass) == frozenset()
    assert detect_flaky_checks(always_fail) == frozenset()


def test_errored_and_partial_runs_prove_nothing() -> None:
    """Only PASSED/FAILED runs carry verdicts; an ERRORED or PARTIAL row
    between them never feeds either direction."""
    runs = [
        _run(check_statuses={"c": "ERRORED"}, run_status="ERRORED"),
        _run(check_statuses={"c": "PASSED"}, run_status="PARTIAL"),
        _run(check_statuses={"c": "PASSED"}, run_status="RUNNING"),
    ]
    assert detect_flaky_checks(runs) == frozenset()


def test_single_anomalous_run_cannot_quarantine() -> None:
    """min_terminal_runs floor: one PASSED + one FAILED is the minimum;
    below it there is no verdict at all."""
    one_run = [_run(check_statuses={"c": "FAILED"}, run_status="FAILED")]
    assert detect_flaky_checks(one_run, min_terminal_runs=2) == frozenset()
    two_runs = [
        _run(check_statuses={"c": "PASSED"}),
        _run(check_statuses={"c": "FAILED"}, run_status="FAILED"),
    ]
    raised_floor = detect_flaky_checks(two_runs, min_terminal_runs=3)
    assert raised_floor == frozenset()


# --- reentry_decision (two-tier cadence) ------------------------------------


def test_zero_elapsed_and_zero_runs_means_wait() -> None:
    decision = reentry_decision(
        detected_at=DETECTED_AT,
        now=DETECTED_AT,
        terminal_runs_since=0,
        cadence=CadencePolicy(every_n_runs=5, interval_seconds=3600),
    )
    assert decision.reentered is False
    assert decision.reason == "cadence_wait"


def test_interval_elapsed_reenters_before_any_nth_run() -> None:
    decision = reentry_decision(
        detected_at=DETECTED_AT,
        now=DETECTED_AT + timedelta(seconds=3601),
        terminal_runs_since=1,
        cadence=CadencePolicy(every_n_runs=5, interval_seconds=3600),
    )
    assert decision.reentered is True
    assert decision.reason == "interval_elapsed"


@pytest.mark.parametrize("runs_since", [5, 10, 15])
def test_nth_run_multiples_reenter(runs_since: int) -> None:
    decision = reentry_decision(
        detected_at=DETECTED_AT,
        now=DETECTED_AT + timedelta(seconds=30),
        terminal_runs_since=runs_since,
        cadence=CadencePolicy(every_n_runs=5, interval_seconds=3600),
    )
    assert decision.reentered is True
    assert decision.reason == f"nth_run:{runs_since}"


@pytest.mark.parametrize("runs_since", [1, 2, 4, 6, 9])
def test_non_multiples_stay_in_tier_one(runs_since: int) -> None:
    decision = reentry_decision(
        detected_at=DETECTED_AT,
        now=DETECTED_AT + timedelta(seconds=30),
        terminal_runs_since=runs_since,
        cadence=CadencePolicy(every_n_runs=5, interval_seconds=3600),
    )
    assert decision.reentered is False


def test_disabled_knob_never_fires() -> None:
    decision = reentry_decision(
        detected_at=DETECTED_AT,
        now=DETECTED_AT + timedelta(hours=99),
        terminal_runs_since=50,
        cadence=CadencePolicy(every_n_runs=0, interval_seconds=0),
    )
    assert decision.reentered is False


# --- PostgreSQL-backed lifecycle --------------------------------------------


@pytest.mark.asyncio
async def test_refresh_is_idempotent_and_events_are_appended() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        task = _task(tenant)
        service = FlakyQuarantineService(engine)
        runs = [
            _run(check_statuses={"tests/flaky.py::one": "PASSED"}),
            _run(
                check_statuses={"tests/flaky.py::one": "FAILED"},
                run_status="FAILED",
                offset_seconds=60,
            ),
        ]

        first = await service.refresh_quarantines(task=task, runs=runs)
        second = await service.refresh_quarantines(task=task, runs=runs)

        assert len(first) == 1
        assert first[0].check_ref == "tests/flaky.py::one"
        assert first[0].active
        assert second == []

        active = await service.list_active(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            task_id=task.task_id,
        )
        assert len(active) == 1
        assert active[0].quarantine_id == first[0].quarantine_id

        async with open_unit_of_work(
            engine,
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
        ) as uow:
            events = await uow.connection.execute(
                text(
                    "SELECT event_type FROM events "
                    "WHERE aggregate_type = 'flaky_quarantine'"
                )
            )
            types = {row[0] for row in events.all()}
            await uow.commit()
        assert "FlakyCheckQuarantined" in types
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_deferred_failure_refs_two_tier_gate() -> None:
    """While cadence says wait the quarantined failure defers; once the
    Nth-run re-entry fires, the plain failure applies again."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        task = _task(tenant)
        clock_offset = {"now": DETECTED_AT}

        class FrozenClock:
            def now(self) -> datetime:
                return clock_offset["now"]

        cadence = CadencePolicy(every_n_runs=5, interval_seconds=86_400)
        service = FlakyQuarantineService(engine, clock=FrozenClock(), cadence=cadence)

        detection_history = [
            _run(check_statuses={"tests/f.py::x": "PASSED"}),
            _run(
                check_statuses={"tests/f.py::x": "FAILED"},
                run_status="FAILED",
                offset_seconds=60,
            ),
        ]
        await service.refresh_quarantines(task=task, runs=detection_history)

        failed_refs = ["tests/f.py::x"]

        def history_with(total_runs: int):
            base = [
                _run(
                    check_statuses={"tests/f.py::x": verdict},
                    run_status=("PASSED" if verdict == "PASSED" else "FAILED"),
                    offset_seconds=60 * index,
                )
                for index, verdict in enumerate(
                    ["PASSED", "FAILED"] + ["PASSED"] * max(total_runs - 2, 0),
                    start=0,
                )
            ]
            return base

        # Tier one: fewer than N terminal runs since detection -> defer.
        clock_offset["now"] = DETECTED_AT + timedelta(minutes=10)
        tier_one = await service.deferred_failure_refs(
            task=task,
            runs=history_with(4),
            failed_check_refs=failed_refs,
        )
        assert tier_one == frozenset({"tests/f.py::x"})

        # Tier two: the 5th terminal run since detection re-enters.
        tier_two = await service.deferred_failure_refs(
            task=task,
            runs=history_with(5),
            failed_check_refs=failed_refs,
        )
        assert tier_two == frozenset()

        # Interval elapsed also re-enters regardless of run counts.
        clock_offset["now"] = DETECTED_AT + timedelta(seconds=86_401)
        after_interval = await service.deferred_failure_refs(
            task=task,
            runs=history_with(2),
            failed_check_refs=failed_refs,
        )
        assert after_interval == frozenset()

        # A never-quarantined ref defers nothing.
        untouched = await service.deferred_failure_refs(
            task=task,
            runs=history_with(4),
            failed_check_refs=["tests/other.py::y"],
            # clock back inside tier one for this call
        )
        assert untouched == frozenset()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_lift_deactivates_and_lift_of_missing_ref_raises() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        task = _task(tenant)
        service = FlakyQuarantineService(engine)
        runs = [
            _run(check_statuses={"tests/l.py::a": "PASSED"}),
            _run(
                check_statuses={"tests/l.py::a": "FAILED"},
                run_status="FAILED",
                offset_seconds=60,
            ),
        ]
        await service.refresh_quarantines(task=task, runs=runs)

        with pytest.raises(Exception, match="no active flaky quarantine"):
            await service.lift(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                task_id=task.task_id,
                check_ref="tests/l.py::never-detected",
                lifted_by="operator-1",
            )

        lifted = await service.lift(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            task_id=task.task_id,
            check_ref="tests/l.py::a",
            lifted_by="operator-1",
        )
        assert lifted.lifted_by == "operator-1"
        assert not lifted.active

        # History retained; nothing blocks a fresh detection cycle.
        active = await service.list_active(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            task_id=task.task_id,
        )
        assert active == []
        recreated = await service.refresh_quarantines(task=task, runs=runs)
        assert len(recreated) == 1
        assert recreated[0].quarantine_id != lifted.quarantine_id

        async with open_unit_of_work(
            engine,
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
        ) as uow:
            events = await uow.connection.execute(
                text(
                    "SELECT event_type FROM events "
                    "WHERE aggregate_type = 'flaky_quarantine' "
                    "AND tenant_id = :tenant AND project_id = :project"
                ),
                {
                    "tenant": str(tenant.tenant_id),
                    "project": str(tenant.project_id),
                },
            )
            types = sorted(row[0] for row in events.all())
            await uow.commit()
        assert types.count("FlakyQuarantineLifted") >= 1
        assert types.count("FlakyCheckQuarantined") == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_partial_unique_index_enforces_one_active_marker() -> None:
    """The partial unique index -- not a NULL-distinct plain UNIQUE --
    makes 'one active quarantine per (task, check_ref)' a database fact."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        task = _task(tenant)
        record = {
            "quarantine_id": str(uuid7()),
            "tenant_id": str(tenant.tenant_id),
            "project_id": str(tenant.project_id),
            "mission_id": str(uuid7()),
            "task_id": str(task.task_id),
            "check_ref": "tests/u.py::dup",
            "detected_at": DETECTED_AT,
            "lifted_at": None,
            "lifted_by": None,
            "sample_size": 2,
            "created_at": DETECTED_AT,
            "updated_at": DETECTED_AT,
        }
        insert_sql = text(
            """
            INSERT INTO flaky_quarantines (
                quarantine_id, tenant_id, project_id, mission_id, task_id,
                check_ref, detected_at, lifted_at, lifted_by, sample_size,
                created_at, updated_at
            ) VALUES (
                :quarantine_id, :tenant_id, :project_id, :mission_id,
                :task_id, :check_ref, :detected_at, :lifted_at, :lifted_by,
                :sample_size, :created_at, :updated_at
            )
            """
        )
        async with open_unit_of_work(
            engine,
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
        ) as uow:
            await uow.connection.execute(insert_sql, record)
            duplicate = dict(record)
            duplicate["quarantine_id"] = str(uuid7())
            with pytest.raises(Exception):  # noqa: B017
                await uow.connection.execute(insert_sql, duplicate)
            await uow.rollback()

        # Lifting frees the slot: a new active marker for the same pair fits.
        async with open_unit_of_work(
            engine,
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
        ) as uow:
            await uow.connection.execute(
                text(
                    "UPDATE flaky_quarantines SET lifted_at = :lift "
                    "WHERE task_id = :t AND check_ref = :c"
                ),
                {
                    "lift": DETECTED_AT + timedelta(hours=1),
                    "t": str(task.task_id),
                    "c": "tests/u.py::dup",
                },
            )
            await uow.connection.execute(insert_sql, dict(record))
            await uow.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_table_rls_is_forced_and_probe_scoped() -> None:
    """Chapter 3.2: FORCE ROW LEVEL SECURITY plus the fail-closed GUC
    policy, observable only through a non-superuser role."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        probe_url = await ensure_rls_probe_role(engine)

        async with open_unit_of_work(
            engine, tenant_id=uuid7(), project_id=None
        ) as admin:
            forced = (
                await admin.connection.execute(
                    text(
                        "SELECT relrowsecurity, relforcerowsecurity "
                        "FROM pg_class WHERE relname = 'flaky_quarantines'"
                    )
                )
            ).one()
            assert tuple(forced) == (True, True)
            policies = (
                await admin.connection.execute(
                    text(
                        "SELECT policyname FROM pg_policies "
                        "WHERE tablename = 'flaky_quarantines'"
                    )
                )
            ).scalars()
            assert "flaky_quarantines_tenant_isolation" in list(policies)
            await admin.commit()

        from sqlalchemy.ext.asyncio import create_async_engine

        probe_engine = create_async_engine(probe_url)
        try:
            other_task = str(uuid7())
            async with open_rls_probe(
                probe_engine,
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
            ) as own:
                await own.execute(
                    text(
                        "INSERT INTO flaky_quarantines ("
                        "quarantine_id, tenant_id, project_id, mission_id,"
                        " task_id, check_ref, detected_at, lifted_at,"
                        " lifted_by, sample_size, created_at, updated_at)"
                        " VALUES (:q, :t, :p, :m, :task, :ref, :now, NULL,"
                        " NULL, 2, :now, :now)"
                    ),
                    {
                        "q": str(uuid7()),
                        "t": str(tenant.tenant_id),
                        "p": str(tenant.project_id),
                        "m": str(uuid7()),
                        "task": str(uuid7()),
                        "ref": "probe/ref",
                        "now": DETECTED_AT,
                    },
                )
                seen = (
                    await own.execute(text("SELECT count(*) FROM flaky_quarantines"))
                ).scalar_one()
                assert seen >= 1

            async with open_rls_probe(
                probe_engine,
                tenant_id=uuid7(),
                project_id=uuid7(),
            ) as foreign:
                foreign_seen = (
                    await foreign.execute(
                        text("SELECT count(*) FROM flaky_quarantines")
                    )
                ).scalar_one()
                assert foreign_seen == 0
                with pytest.raises(Exception):  # noqa: B017
                    await foreign.execute(
                        text(
                            "INSERT INTO flaky_quarantines ("
                            "quarantine_id, tenant_id, project_id, mission_id,"
                            " task_id, check_ref, detected_at, lifted_at,"
                            " lifted_by, sample_size, created_at, updated_at)"
                            " VALUES (:q, :t, :p, :m, :task, :ref, :now, NULL,"
                            " NULL, 2, :now, :now)"
                        ),
                        {
                            "q": str(uuid7()),
                            "t": str(tenant.tenant_id),
                            "p": str(tenant.project_id),
                            "m": str(uuid7()),
                            "task": other_task,
                            "ref": "probe/foreign-write",
                            "now": DETECTED_AT,
                        },
                    )
        finally:
            await probe_engine.dispose()
    finally:
        await engine.dispose()
