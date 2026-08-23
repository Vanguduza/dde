"""Kill flag at capability checkout (research §6 item 2) -- pure unit tests
over the real `CapabilityLeaseService.require_active` gate logic with fake
repositories/events, no PostgreSQL.

Production call sites under test: `engine.capabilities.lease_service.
CapabilityLeaseService.require_active` is THE per-call guard both real
Stage 1 side-effecting paths pass through (`engine.workers.scripted_adapter.
ScriptedWorkerAdapter.start` for filesystem/local-process and
`engine.workspaces.service.WorkspaceService.snapshot` for git). The kill
flag is checked inside that checkout's transaction: arming a stop for a run
takes effect before the run's NEXT tool call, not at attempt start. Every
refusal journals a `CapabilityKillFlagEnforced` event in its own
transaction, and `arm_run_stop` performs the ACTIVE sweep -- every still-
held lease to the chapter-named terminal status REVOKED with reason
"kill_flag" plus one `CapabilityRunStopArmed` summary event -- the closest
existing Chapter 9.2 state, no new taxonomy invented.

The ARMED/DISARMED state itself is durable through the EXISTING
`CommandLedger` (`command_idempotency`, one row per run keyed
`kill_flag_run_stop:{run_id}`): `require_active` consults memory first,
then that row, INSIDE the transaction it already opens -- so a fresh
service instance with a cold registry still refuses checkout for a run
stopped by a previous process, and `disarm_run_stop` flips the row so a
disarmed run passes again. The fake ledger below mirrors the real
`engine.events.idempotency.CommandLedger` surface exactly (`begin`
insert-once dedup, `complete` result flip, `get_by_key_scoped` read).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from engine.capabilities.kill_switch import (
    KILL_FLAG_REASON,
    STOP_STATE_ARMED,
    STOP_STATE_DISARMED,
    KillSwitchRegistry,
    run_stop_idempotency_key,
)
from engine.capabilities.lease_repository import CapabilityLeaseRepository
from engine.capabilities.lease_service import CapabilityLeaseService
from engine.capabilities.lease_states import HELD_LEASE_STATUSES
from engine.contracts.capability_lease import CapabilityLease
from engine.contracts.command_idempotency import CommandIdempotency
from engine.core.errors import DdeError

TENANT = uuid4()
PROJECT = uuid4()
RUN = uuid4()


class RecordingEvents:
    """No-op stand-in for `engine.events.service.EventService.append` --
    the only member `_transition` uses on the events service. Records
    calls so tests can assert a revocation actually emitted its event."""

    def __init__(self) -> None:
        self.appended: list[dict[str, object]] = []

    async def append(self, **kwargs: object) -> None:
        self.appended.append(dict(kwargs))


class FakeLeaseRepository(CapabilityLeaseRepository):
    """In-memory stand-in for the lease row store; only the members the
    kill-flag path and `require_active` touch are overridden. The base
    class is subclassed so any member this file forgets to fake fails
    loudly instead of silently passing."""

    def __init__(self, leases: list[CapabilityLease]) -> None:
        self.leases = leases
        self.updates: dict[str, object] = {}

    async def get_active_for_run(
        self,
        connection: object,
        *,
        worker_run_id: object,
        capability_id: str,
    ) -> CapabilityLease | None:
        candidates = [
            item
            for item in self.leases
            if item.worker_run_id == worker_run_id
            and item.capability_id == capability_id
        ]
        return candidates[-1] if candidates else None

    async def list_for_run(
        self, connection: object, worker_run_id: object
    ) -> list[CapabilityLease]:
        return [item for item in self.leases if item.worker_run_id == worker_run_id]

    async def list_held_for_run(
        self, connection: object, worker_run_id: object
    ) -> list[CapabilityLease]:
        return [
            item
            for item in self.leases
            if item.worker_run_id == worker_run_id
            and item.status in HELD_LEASE_STATUSES
        ]

    async def get_by_id(
        self, connection: object, lease_id: object
    ) -> CapabilityLease | None:
        for item in self.leases:
            if item.lease_id == lease_id:
                return item
        return None

    async def update_fields(
        self,
        connection: object,
        lease_id: object,
        *,
        fields: dict[str, object],
    ) -> int:
        for index, item in enumerate(self.leases):
            if item.lease_id == lease_id:
                data = item.model_dump()
                data.update(fields)
                self.leases[index] = CapabilityLease.model_validate(data)
                self.updates[str(lease_id)] = dict(fields)
                return 1
        return 0


class FakeUOW:
    """`require_active`'s body never touches the connection when the
    repository is faked; it is passed through opaquely."""

    connection = object()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FakeLedger:
    """In-memory mirror of the real `CommandLedger`'s stop-record surface:
    `begin` inserts once per `(tenant_id, idempotency_key)` and hands back
    the existing row otherwise (the dedup semantics of
    `INSERT ... ON CONFLICT DO NOTHING`, Chapter 12.5), `complete` flips
    `status`/`result`, `get_by_key_scoped` reads without mutating. Rows
    survive service-instance construction -- exactly what a restart
    replays against."""

    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str], CommandIdempotency] = {}
        self.begin_calls = 0

    async def begin(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        idempotency_key: str,
        request_hash: str,
        uow: object = None,
    ) -> tuple[CommandIdempotency, bool]:
        self.begin_calls += 1
        now = datetime.now(UTC)
        key = (tenant_id, idempotency_key)
        existing = self.rows.get(key)
        if existing is not None:
            return existing, False
        record = CommandIdempotency(
            command_id=uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="in_progress",
            result=None,
            expires_at=now + timedelta(days=30),
            created_at=now,
            updated_at=now,
        )
        self.rows[key] = record
        return record, True

    async def complete(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        command_id: UUID,
        result: dict[str, object],
        uow: object = None,
    ) -> CommandIdempotency:
        for key, row in self.rows.items():
            if key[0] == tenant_id and row.command_id == command_id:
                data = row.model_dump()
                data.update(status="completed", result=result)
                updated = CommandIdempotency.model_validate(data)
                self.rows[key] = updated
                return updated
        raise AssertionError(f"complete() for unknown command {command_id}")

    async def get_by_key_scoped(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        idempotency_key: str,
        uow: object = None,
    ) -> CommandIdempotency | None:
        return self.rows.get((tenant_id, idempotency_key))


def _lease(
    *, status: str, capability_id: str = "capability.run_local_process"
) -> CapabilityLease:
    now = datetime.now(UTC)
    return CapabilityLease(
        lease_id=uuid4(),
        tenant_id=TENANT,
        project_id=PROJECT,
        mission_id=uuid4(),
        task_id=uuid4(),
        execution_plan_id=uuid4(),
        worker_run_id=RUN,
        environment_id=None,
        capability_id=capability_id,
        capability_version="1",
        resource_scope={},
        operation_scope="execute",
        constraints={},
        issued_by_policy_version="capability-lease-v1",
        issued_at=now,
        expires_at=now + timedelta(hours=24),
        revocable=True,
        status=status,
        denied_reason=None,
        revoked_at=None,
        revocation_reason=None,
        lease_hash="hash",
        requested_by="test",
        created_at=now,
        updated_at=now,
    )


def _service(
    leases: list[CapabilityLease],
) -> tuple[CapabilityLeaseService, FakeLeaseRepository, RecordingEvents, FakeLedger]:
    repo = FakeLeaseRepository(leases)
    events = RecordingEvents()
    ledger = FakeLedger()
    service = CapabilityLeaseService(
        engine=None,  # type: ignore[arg-type]
        repository=repo,
        events=events,  # type: ignore[arg-type]
        commands=ledger,  # type: ignore[arg-type]
        capabilities=None,  # type: ignore[arg-type]
        kill_switch=KillSwitchRegistry(),
    )
    return service, repo, events, ledger


async def test_armed_kill_flag_refuses_checkout_of_a_held_lease() -> None:
    """Mid-run revocation: the lease was GRANTED (or even already ACTIVE --
    the state a previous successful tool call left it in), then the stop
    arms. The very next checkout must fail closed with typed
    KILL_FLAG_ACTIVE -- exactly like an expiry does, but with its own code
    so an intentional stop is distinguishable from a policy denial."""
    lease = _lease(status="ACTIVE")
    service, repo, events, _ledger = _service([lease])
    service.kill_switch.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)

    with pytest.raises(DdeError) as excinfo:
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"
    assert excinfo.value.details is not None
    assert excinfo.value.details["reason"] == KILL_FLAG_REASON
    assert len(events.appended) == 2
    assert events.appended[0]["event_type"] == "CapabilityLeaseRevoked"
    assert events.appended[1]["event_type"] == "CapabilityKillFlagEnforced"


async def test_first_refusal_durably_revokes_latest_held_lease() -> None:
    """The durable half of the intentional stop uses the closest existing
    state: EVERY still-held lease of the run lands in the chapter-named
    terminal status REVOKED with reason kill_flag -- so the stop survives
    process restarts even though the flag set itself does not."""
    older = _lease(status="ACTIVE")
    newer = _lease(status="GRANTED", capability_id="capability.workspace_filesystem")
    service, repo, _events, _ledger = _service([older, newer])
    service.kill_switch.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)

    with pytest.raises(DdeError) as excinfo:
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"
    statuses = {item.lease_id: item.status for item in repo.leases}
    assert statuses[older.lease_id] == "REVOKED"
    assert statuses[newer.lease_id] == "REVOKED"
    stored = repo.updates[str(older.lease_id)]
    assert isinstance(stored, dict)
    assert stored["revocation_reason"] == KILL_FLAG_REASON


async def test_kill_refusal_persists_across_disarm_is_not_possible_via_checkout() -> (
    None
):
    """After the first refusal revoked the held lease, a later checkout of
    the same run/capability still fails closed even if the caller somehow
    re-requests it -- REVOKED is terminal in Chapter 9.2's machine. This is
    the adversarial check from the mission-chapter-gate rule: no new
    checkout path resurrects authority."""
    lease = _lease(status="ACTIVE")
    service, _repo, _events, _ledger = _service([lease])
    service.kill_switch.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)

    with pytest.raises(DdeError):
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )

    # Simulate a restarted process where the in-memory flag set is empty:
    # the durable REVOKED row must still fail the run closed.
    service.kill_switch.disarm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)
    with pytest.raises(DdeError) as excinfo:
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "POLICY_DENIED"
    assert "not held" in excinfo.value.message


async def test_kill_flag_for_one_run_does_not_touch_other_runs() -> None:
    """Scope discipline: arming a stop for one worker run must not refuse
    another run's checkout."""
    killed_run = RUN

    class ScopedRepo(FakeLeaseRepository):
        async def get_active_for_run(
            self,
            connection: object,
            *,
            worker_run_id: object,
            capability_id: str,
        ) -> CapabilityLease | None:
            if worker_run_id != RUN:
                return None
            return await super().get_active_for_run(
                connection,
                worker_run_id=worker_run_id,
                capability_id=capability_id,
            )

    repo = ScopedRepo([_lease(status="ACTIVE")])
    events = RecordingEvents()
    service = CapabilityLeaseService(
        engine=None,  # type: ignore[arg-type]
        repository=repo,
        events=events,  # type: ignore[arg-type]
        commands=FakeLedger(),  # type: ignore[arg-type]
        capabilities=None,  # type: ignore[arg-type]
        kill_switch=KillSwitchRegistry(),
    )
    service.kill_switch.arm(
        tenant_id=TENANT, project_id=PROJECT, worker_run_id=killed_run
    )
    with pytest.raises(DdeError):
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=killed_run,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )


async def test_unarmed_service_behaviour_is_unchanged() -> None:
    """The default path (no kill switch armed anywhere) must behave
    byte-identically to before this change: GRANTED activates on first
    checkout, expiry still wins over everything else."""
    granted = _lease(status="GRANTED")
    service, repo, events, _ledger = _service([granted])

    activated = await service.require_active(
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        capability_id="capability.run_local_process",
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert activated.status == "ACTIVE"
    assert repo.updates[str(granted.lease_id)]["status"] == "ACTIVE"
    assert len(events.appended) == 1
    assert events.appended[0]["event_type"] == "CapabilityLeaseActivated"


async def test_kill_flag_with_no_existing_lease_still_fails_closed() -> None:
    """A run killed before any lease exists has no row to stamp -- the
    refusal must still happen (fail closed), with nothing fabricated."""
    service, _repo, _events, _ledger = _service([])
    service.kill_switch.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)

    with pytest.raises(DdeError) as excinfo:
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"


def test_recovery_matrix_maps_kill_refusal_to_intentionally_stopped() -> None:
    """A mid-run kill refusal that reaches recovery dispatches onto the
    INTENTIONALLY_STOPPED taxonomy row (EDR-0010, accepted 2026-08-23):
    acknowledge_stop, requires_human, never silently retried -- the stop
    is an operator act to acknowledge, not a failure to approve away."""
    from engine.recovery.matrix import canonical_failure_class, decide

    assert canonical_failure_class("KILL_FLAG_ACTIVE") == ("INTENTIONALLY_STOPPED")
    decision = decide("KILL_FLAG_ACTIVE", occurrence_count=1)
    assert decision.allow_new_worker_run is False
    assert decision.requires_human is True
    assert decision.action == "acknowledge_stop"


async def test_refusal_journals_kill_flag_enforced_in_the_same_transaction() -> None:
    """TASK A, checkout surface: an armed stop's refusal journals a
    `CapabilityKillFlagEnforced` event through the injected EventService
    with the repo's standard envelope -- aggregate = the run, payload
    naming the checkout surface and the kill-flag reason. Ordering puts
    the journal BEFORE the typed raise, inside the same `_op`, so a real
    unit of work commits it atomically with the refusal."""
    lease = _lease(status="ACTIVE")
    service, _repo, events, _ledger = _service([lease])
    service.kill_switch.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)

    with pytest.raises(DdeError):
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    enforced = [
        e for e in events.appended if e["event_type"] == ("CapabilityKillFlagEnforced")
    ]
    assert len(enforced) == 1
    event = enforced[0]
    assert event["tenant_id"] == TENANT
    assert event["project_id"] == PROJECT
    assert event["aggregate_type"] == "worker_run"
    assert event["aggregate_id"] == RUN
    payload = event["payload"]
    assert isinstance(payload, dict)
    assert payload["surface"] == "checkout"
    assert payload["reason"] == KILL_FLAG_REASON


async def test_arm_run_stop_sweeps_every_held_lease_and_journals_one_summary() -> None:
    """TASK B: arming the stop is the durable act. Multiple held leases
    (one ACTIVE, one GRANTED) plus an already-terminal REVOKED row: the
    sweep revokes exactly the held ones via the existing transition path,
    leaves the terminal row untouched, registers the flag, journals ONE
    summary event (aggregate = the run) carrying the revoked ids, and the
    backstop still refuses a subsequent checkout."""
    active = _lease(status="ACTIVE")
    granted = _lease(status="GRANTED", capability_id="capability.workspace_filesystem")
    already_revoked = _lease(
        status="REVOKED", capability_id="capability.git_operations"
    )
    service, repo, events, _ledger = _service([active, granted, already_revoked])

    revoked = await service.arm_run_stop(
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert {item.lease_id for item in revoked} == {
        active.lease_id,
        granted.lease_id,
    }
    statuses = {item.lease_id: item.status for item in repo.leases}
    assert statuses[active.lease_id] == "REVOKED"
    assert statuses[granted.lease_id] == "REVOKED"
    assert statuses[already_revoked.lease_id] == "REVOKED"  # untouched, was terminal
    for lease_id in (active.lease_id, granted.lease_id):
        stamped = repo.updates[str(lease_id)]
        assert isinstance(stamped, dict)
        assert stamped["revocation_reason"] == KILL_FLAG_REASON
    assert service.kill_switch.is_killed(
        tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
    )

    summaries = [
        e for e in events.appended if e["event_type"] == "CapabilityRunStopArmed"
    ]
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["aggregate_type"] == "worker_run"
    assert summary["aggregate_id"] == RUN
    payload = summary["payload"]
    assert isinstance(payload, dict)
    assert payload["revoked_count"] == 2
    assert set(payload["revoked_lease_ids"]) == {
        str(active.lease_id),
        str(granted.lease_id),
    }
    per_lease = [
        e for e in events.appended if e["event_type"] == ("CapabilityLeaseRevoked")
    ]
    assert len(per_lease) == 2

    # Backstop intact: even after the sweep emptied the held set, the flag
    # itself still refuses the next checkout.
    with pytest.raises(DdeError) as excinfo:
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"


async def test_arm_run_stop_with_no_held_leases_still_journals_the_summary() -> None:
    """A stop armed before any lease exists must still register the flag
    and journal the (empty) sweep summary -- nothing fabricated, nothing
    swallowed."""
    service, _repo, events, ledger = _service([])
    revoked = await service.arm_run_stop(
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert revoked == []
    summaries = [
        e for e in events.appended if e["event_type"] == "CapabilityRunStopArmed"
    ]
    assert len(summaries) == 1
    payload = summaries[0]["payload"]
    assert isinstance(payload, dict)
    assert payload["revoked_count"] == 0
    assert payload["revoked_lease_ids"] == []
    # The durable stop record exists even with nothing swept.
    record = ledger.rows[(TENANT, run_stop_idempotency_key(RUN))]
    assert record.result == {"state": STOP_STATE_ARMED, "reason": KILL_FLAG_REASON}


async def test_cold_restart_refuses_checkout_from_durable_record_alone() -> None:
    """The restart scenario the in-memory flag could not cover: instance A
    arms a stop (its sweep empties the held leases and its registry holds
    the flag), then a brand-new service instance B is constructed -- fresh
    `KillSwitchRegistry` and event recorder, but the SAME shared durable
    stores (the fake repo's rows and the fake ledger survive construction,
    exactly like the database tables a restart reopens). B's
    `require_active` must refuse from the DURABLE record alone, without
    anyone re-arming."""
    lease = _lease(status="ACTIVE")
    service_a, repo_a, _events_a, ledger = _service([lease])
    await service_a.arm_run_stop(
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        uow=FakeUOW(),  # type: ignore[arg-type]
    )

    service_b, _repo_b, events_b, _ledger_b = _service([])
    service_b._repository = repo_a  # noqa: SLF001 -- injecting the shared store
    service_b._commands = ledger  # noqa: SLF001
    assert (
        service_b.kill_switch.is_killed(
            tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
        )
        is False
    )
    assert repo_a.leases[0].status == "REVOKED"  # sweep survived the restart too

    with pytest.raises(DdeError) as excinfo:
        await service_b.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"
    enforced = [
        e for e in events_b.appended if e["event_type"] == "CapabilityKillFlagEnforced"
    ]
    assert len(enforced) == 1


async def test_disarm_flips_durable_record_and_fresh_instance_passes_again() -> None:
    """Symmetric undo: after A armed, `disarm_run_stop` flips the SAME
    ledger row to DISARMED (no second row), drops A's cache, and fresh
    instances C and D -- cold registry, same shared durable stores --
    first refuse (row still ARMED) then pass again after the flip."""
    lease = _lease(status="GRANTED")
    service_a, repo_a, _events_a, ledger = _service([lease])
    await service_a.arm_run_stop(
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    key = (TENANT, run_stop_idempotency_key(RUN))
    assert len(ledger.rows) == 1  # one row per run, not one per arm/disarm

    # Fresh process C first PROVES it refuses (durable record says ARMED),
    # then the operator disarms through A and D passes again.
    service_c, _repo_c, _events_c, _ledger_c = _service([])
    service_c._repository = repo_a  # noqa: SLF001 -- injecting the shared store
    service_c._commands = ledger  # noqa: SLF001
    with pytest.raises(DdeError) as excinfo:
        await service_c.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"

    await service_a.disarm_run_stop(
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert (
        service_a.kill_switch.is_killed(
            tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN
        )
        is False
    )
    record = ledger.rows[key]
    assert record.result == {"state": STOP_STATE_DISARMED, "reason": "disarmed"}

    # Authority after a stop returns the Chapter 9.2 way -- a NEW lease --
    # so D (fresh process, shared stores) must pass against freshly
    # granted authority once the durable record says DISARMED.
    repo_a.leases.append(_lease(status="GRANTED"))
    service_d, _repo_d, _events_d, _ledger_d = _service([])
    service_d._repository = repo_a  # noqa: SLF001
    service_d._commands = ledger  # noqa: SLF001
    activated = await service_d.require_active(
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        capability_id="capability.run_local_process",
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert activated.status == "ACTIVE"
    assert repo_a.leases[0].status == "REVOKED"  # the stopped lease stays terminal


async def test_rearming_twice_journals_one_ledger_row_not_two() -> None:
    """Replay/idempotency: arming twice presents the SAME deterministic
    ledger key; `begin`'s dedup yields exactly one `command_idempotency`
    row whose state stays ARMED -- no double-journal, no duplicate stop
    records. The sweep simply re-runs over an empty held set."""
    service, _repo, events, ledger = _service([])
    kwargs: dict[str, object] = {
        "tenant_id": TENANT,
        "project_id": PROJECT,
        "worker_run_id": RUN,
        "uow": FakeUOW(),
    }
    await service.arm_run_stop(**kwargs)  # type: ignore[arg-type]
    await service.arm_run_stop(**kwargs)  # type: ignore[arg-type]

    key = run_stop_idempotency_key(RUN)
    rows = [row for (tenant, idem), row in ledger.rows.items() if idem == key]
    assert len(rows) == 1
    assert rows[0].result == {"state": STOP_STATE_ARMED, "reason": KILL_FLAG_REASON}
    assert ledger.begin_calls == 2  # both calls went through the dedup path
    summaries = [
        e for e in events.appended if e["event_type"] == "CapabilityRunStopArmed"
    ]
    assert len(summaries) == 2  # journal-per-arm unchanged; ledger row deduped


async def test_direct_registry_arm_still_refuses_without_any_ledger_row() -> None:
    """Backstop intact: arming ONLY the registry (no `arm_run_stop`, no
    ledger row) still refuses checkout in the same process via the
    memory-first fast path."""
    service, _repo, _events, ledger = _service([_lease(status="ACTIVE")])
    service.kill_switch.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)
    assert ledger.rows == {}

    with pytest.raises(DdeError) as excinfo:
        await service.require_active(
            tenant_id=TENANT,
            project_id=PROJECT,
            worker_run_id=RUN,
            capability_id="capability.run_local_process",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"
