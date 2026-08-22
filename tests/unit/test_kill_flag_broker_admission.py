"""Kill flag at credential-broker admission (research §6 gap closure) --
pure unit tests over the real `CredentialBrokerService` admission gate
(`_require_active_lease`) with fake repositories/events/ledger, no
PostgreSQL.

Production seam under test: `engine.capabilities.broker.service.
CredentialBrokerService._require_active_lease` re-reads the lease row live
inside every admission and consults the SAME run-stop state the lease
checkout guard checks -- memory first
(`engine.capabilities.lease_service.SHARED_KILL_SWITCH`), then the DURABLE
`command_idempotency` stop row through the EXISTING `CommandLedger`. An
armed stop refuses `issue()`/`renew()` for the killed run with typed
KILL_FLAG_ACTIVE BEFORE any credential material is derived -- including
from a fresh process whose registry is cold but whose durable stop row
says ARMED. Every refusal journals a `CredentialKillFlagEnforced` event in
the refusing transaction, live handles of a stopped run are revoked at arm
time via `revoke_handles_for_leases` (the sweep half of an intentional
stop), and `disarm_run_stop` flips the durable row so a disarmed run
passes again after a restart -- exactly as before at verify time
otherwise.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from engine.capabilities.broker.provider import (
    CredentialScope,
    ProviderIssuedCredential,
)
from engine.capabilities.broker.repository import CredentialHandleRepository
from engine.capabilities.broker.service import CredentialBrokerService
from engine.capabilities.kill_switch import (
    KILL_FLAG_REASON,
    STOP_STATE_DISARMED,
    KillSwitchRegistry,
    read_durable_run_stop,
    record_run_stop,
    run_stop_idempotency_key,
)
from engine.capabilities.lease_repository import CapabilityLeaseRepository
from engine.contracts.capability_lease import CapabilityLease
from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.credential_handle import CredentialHandle
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex

TENANT = uuid4()
PROJECT = uuid4()
RUN = uuid4()
OTHER_RUN = uuid4()
MISSION = uuid4()
TASK = uuid4()
LEASE_ID = uuid4()

#: The RecordingProvider's fixture secret -- asserted against in verify()
#: checks only, never a real credential.
FIXTURE_SECRET = "recording-provider-secret-value"  # noqa: S105 -- fixture value


class RecordingEvents:
    """No-op stand-in for `engine.events.service.EventService.append`.
    Records calls so tests can assert a kill-flag refusal emits nothing --
    the refusal precedes any mutation, unlike the checkout path which
    durably revokes."""

    def __init__(self) -> None:
        self.appended: list[dict[str, object]] = []

    async def append(self, **kwargs: object) -> None:
        self.appended.append(dict(kwargs))


class RecordingProvider:
    """Stand-in for `LocalSecretProvider` that records every `issue` call,
    so tests can assert an armed stop derives NO secret material at all --
    not merely that derived material went undelivered."""

    provider_id = "recording_test"

    def __init__(self) -> None:
        self.issue_calls: list[CredentialScope] = []

    def issue(self, scope: CredentialScope) -> ProviderIssuedCredential:
        self.issue_calls.append(scope)
        return ProviderIssuedCredential(
            secret_value="recording-provider-secret-value",  # noqa: S106 -- fixture value
            provider_ref=None,
        )

    def revoke(self, provider_ref: str | None) -> None:
        return None


class FakeLeaseRepository(CapabilityLeaseRepository):
    """In-memory stand-in for the lease row store; only `get_by_id`, the
    one member `_require_active_lease` touches, is overridden. The base
    class is subclassed so any member this file forgets to fake fails
    loudly instead of silently passing."""

    def __init__(self, leases: list[CapabilityLease]) -> None:
        self.leases = leases

    async def get_by_id(
        self, connection: object, lease_id: object
    ) -> CapabilityLease | None:
        for item in self.leases:
            if item.lease_id == lease_id:
                return item
        return None


class FakeHandleRepository(CredentialHandleRepository):
    """In-memory stand-in for `credential_handles`; only `insert_handle`,
    `get_by_id`, `update_fields` and `list_for_lease`, the members the
    tested paths touch, are overridden."""

    def __init__(self) -> None:
        self.handles: list[CredentialHandle] = []

    async def insert_handle(self, connection: object, record: CredentialHandle) -> None:
        self.handles.append(record)

    async def get_by_id(
        self, connection: object, handle_id: UUID
    ) -> CredentialHandle | None:
        for item in self.handles:
            if item.handle_id == handle_id:
                return item
        return None

    async def update_fields(
        self,
        connection: object,
        handle_id: UUID,
        *,
        fields: dict[str, object],
    ) -> int:
        for index, item in enumerate(self.handles):
            if item.handle_id == handle_id:
                data = item.model_dump()
                data.update(fields)
                self.handles[index] = CredentialHandle.model_validate(data)
                return 1
        return 0

    async def list_for_lease(
        self, connection: object, lease_id: UUID
    ) -> list[CredentialHandle]:
        return [item for item in self.handles if item.lease_id == lease_id]


class FakeCommandLedger:
    """In-memory mirror of the real `CommandLedger` surface the broker and
    the durable stop record use: every `begin` claims an unseen key and
    hands back the existing row for a seen one (the dedup semantics of
    `INSERT ... ON CONFLICT DO NOTHING`, Chapter 12.5), `complete` flips
    `status`/`result`, `get_by_key_scoped` reads without mutating. Rows
    persist across service-instance construction -- what a restart replays
    against."""

    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str], CommandIdempotency] = {}

    async def begin(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        idempotency_key: str,
        request_hash: str,
        uow: object = None,
    ) -> tuple[CommandIdempotency, bool]:
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


class FakeUOW:
    """Admission never touches the connection when repositories are faked;
    it is passed through opaquely."""

    connection = object()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _lease(
    *, worker_run_id: UUID, status: str = "ACTIVE", lease_id: UUID | None = None
) -> CapabilityLease:
    now = datetime.now(UTC)
    return CapabilityLease(
        lease_id=lease_id or LEASE_ID,
        tenant_id=TENANT,
        project_id=PROJECT,
        mission_id=MISSION,
        task_id=TASK,
        execution_plan_id=uuid4(),
        worker_run_id=worker_run_id,
        environment_id=None,
        capability_id="capability.run_local_process",
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


def _handle(*, worker_run_id: UUID) -> CredentialHandle:
    now = datetime.now(UTC)
    return CredentialHandle(
        handle_id=uuid4(),
        tenant_id=TENANT,
        project_id=PROJECT,
        mission_id=MISSION,
        task_id=TASK,
        worker_run_id=worker_run_id,
        lease_id=LEASE_ID,
        capability_id="capability.run_local_process",
        provider_id="recording_test",
        provider_ref=None,
        resource_scope={},
        issued_by_policy_version="capability-lease-v1",
        secret_hash=sha256_hex("recording-provider-secret-value"),
        status="ISSUED",
        issued_at=now,
        expires_at=now + timedelta(minutes=15),
        revoked_at=None,
        revocation_reason=None,
        supersedes_handle_id=None,
        superseded_by_handle_id=None,
        requested_by="test",
        created_at=now,
        updated_at=now,
    )


def _service(
    leases: list[CapabilityLease],
) -> tuple[
    CredentialBrokerService,
    KillSwitchRegistry,
    RecordingProvider,
    RecordingEvents,
    FakeHandleRepository,
    FakeCommandLedger,
]:
    provider = RecordingProvider()
    events = RecordingEvents()
    registry = KillSwitchRegistry()
    handles = FakeHandleRepository()
    ledger = FakeCommandLedger()
    broker = CredentialBrokerService(
        engine=None,  # type: ignore[arg-type]
        repository=handles,
        lease_repository=FakeLeaseRepository(leases),
        events=events,  # type: ignore[arg-type]
        commands=ledger,  # type: ignore[arg-type]
        provider=provider,
        # Explicit injection of the SHARED default's type twin keeps the
        # test hermetic; the default-constructor path (shared registry) is
        # pinned by the identity assertion below.
        kill_switch=registry,
    )
    return broker, registry, provider, events, handles, ledger


async def test_default_constructor_reuses_the_shared_registry() -> None:
    """No second registry may exist: a bare `CredentialBrokerService(engine)`
    must consult exactly the module-level instance the lease service
    checks, so arming through either service gates both surfaces."""
    from engine.capabilities.broker.service import CredentialBrokerService as Svc
    from engine.capabilities.lease_service import SHARED_KILL_SWITCH

    broker = Svc(engine=None)  # type: ignore[arg-type]
    assert broker._kill_switch is SHARED_KILL_SWITCH


async def test_armed_kill_flag_refuses_issue_and_derives_no_material() -> None:
    """The closed hole: run holds an ACTIVE lease, then the stop arms.
    `issue()` must fail closed with typed KILL_FLAG_ACTIVE and the provider
    must NEVER be asked to derive a secret -- not merely have its output
    withheld."""
    broker, registry, provider, events, _handles, _ledger = _service(
        [_lease(worker_run_id=RUN)]
    )
    registry.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)

    with pytest.raises(DdeError) as excinfo:
        await broker.issue(
            tenant_id=TENANT,
            project_id=PROJECT,
            lease_id=LEASE_ID,
            requested_by="test",
            idempotency_key="issue:killed",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"
    assert excinfo.value.details is not None
    assert excinfo.value.details["reason"] == KILL_FLAG_REASON
    assert excinfo.value.details["worker_run_id"] == str(RUN)
    assert provider.issue_calls == []
    # The refusal's own enforcement journal is the ONLY event: no
    # issuance happened, so nothing else was emitted.
    assert len(events.appended) == 1
    assert events.appended[0]["event_type"] == "CredentialKillFlagEnforced"


async def test_armed_kill_flag_refuses_renewal_of_a_live_handle() -> None:
    """A handle issued BEFORE the stop arms cannot be renewed into fresh
    material afterwards: `renew()` hits the same admission gate."""
    handle = _handle(worker_run_id=RUN)
    broker, registry, provider, _events, handles, _ledger = _service(
        [_lease(worker_run_id=RUN)]
    )
    handles.handles.append(handle)
    first = await broker.renew(
        tenant_id=TENANT,
        project_id=PROJECT,
        handle_id=handle.handle_id,
        requested_by="test",
        idempotency_key="renew:before-stop",
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert first.secret_value is not None

    registry.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)
    with pytest.raises(DdeError) as excinfo:
        await broker.renew(
            tenant_id=TENANT,
            project_id=PROJECT,
            handle_id=first.handle.handle_id,
            requested_by="test",
            idempotency_key="renew:after-stop",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"
    # Exactly one derivation: the pre-stop renewal. Nothing post-arm.
    assert len(provider.issue_calls) == 1


async def test_disarmed_broker_behaviour_is_unchanged() -> None:
    """With no flag armed anywhere, issuance behaves byte-identically to
    before this change: fresh secret delivered once, live handle verifiable
    against it."""
    broker, _registry, provider, _events, _handles, _ledger = _service(
        [_lease(worker_run_id=RUN)]
    )

    issued = await broker.issue(
        tenant_id=TENANT,
        project_id=PROJECT,
        lease_id=LEASE_ID,
        requested_by="test",
        idempotency_key="issue:clean",
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert issued.secret_value is not None
    assert issued.handle.status == "ISSUED"
    assert len(provider.issue_calls) == 1
    assert (
        await broker.verify(
            tenant_id=TENANT,
            project_id=PROJECT,
            handle_id=issued.handle.handle_id,
            secret_value=issued.secret_value,
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
        is True
    )


async def test_revoked_lease_path_is_unchanged_and_not_misreported_as_kill() -> None:
    """A REVOKED lease denies admission with POLICY_DENIED exactly as
    before -- the kill-flag gate adds a distinct outcome, it does not
    overwrite or shadow the pre-existing denial taxonomy. Also proves the
    gate keys on the row's OWN run: the flag here is armed for a DIFFERENT
    run, so this denial comes from the lease status alone."""
    revoked = _lease(worker_run_id=RUN, status="REVOKED")
    broker, registry, _provider, _events, _handles, _ledger = _service([revoked])
    registry.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=OTHER_RUN)

    with pytest.raises(DdeError) as excinfo:
        await broker.issue(
            tenant_id=TENANT,
            project_id=PROJECT,
            lease_id=revoked.lease_id,
            requested_by="test",
            idempotency_key="issue:revoked-lease",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "POLICY_DENIED"


async def test_kill_flag_for_one_run_does_not_touch_other_runs() -> None:
    """Scope discipline: arming a stop for one worker run must not refuse
    another run's credential admission against its own lease."""
    broker, registry, _provider, _events, _handles, _ledger = _service(
        [
            _lease(worker_run_id=RUN),
            _lease(worker_run_id=OTHER_RUN, lease_id=uuid4()),
        ]
    )
    registry.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=OTHER_RUN)

    issued = await broker.issue(
        tenant_id=TENANT,
        project_id=PROJECT,
        lease_id=LEASE_ID,
        requested_by="test",
        idempotency_key="issue:survivor-run",
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert issued.secret_value is not None


async def test_refusal_journals_credential_admission_enforcement() -> None:
    """TASK A, credential-admission surface: an armed stop's refusal
    journals a `CredentialKillFlagEnforced` event through the injected
    EventService with the repo's standard envelope -- aggregate = the
    lease involved, payload naming the surface, the run and the
    capability. Ordering puts the journal BEFORE the typed raise inside
    `_require_active_lease`'s caller `_op`, so a real unit of work
    commits it atomically with the refusal."""
    broker, registry, provider, events, _handles, _ledger = _service(
        [_lease(worker_run_id=RUN)]
    )
    registry.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)

    with pytest.raises(DdeError):
        await broker.issue(
            tenant_id=TENANT,
            project_id=PROJECT,
            lease_id=LEASE_ID,
            requested_by="test",
            idempotency_key="issue:journalled",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert len(events.appended) == 1
    event = events.appended[0]
    assert event["tenant_id"] == TENANT
    assert event["project_id"] == PROJECT
    assert event["event_type"] == "CredentialKillFlagEnforced"
    assert event["aggregate_type"] == "capability_lease"
    assert event["aggregate_id"] == LEASE_ID
    payload = event["payload"]
    assert isinstance(payload, dict)
    assert payload["surface"] == "credential_admission"
    assert payload["worker_run_id"] == str(RUN)
    assert payload["capability_id"] == "capability.run_local_process"
    assert payload["reason"] == KILL_FLAG_REASON
    # Still zero derivations: the journal precedes nothing secret-shaped.
    assert provider.issue_calls == []


async def test_disarmed_broker_journals_nothing_on_refusal_free_paths() -> None:
    """With no flag armed anywhere, a POLICY_DENIED admission (REVOKED
    lease) emits NO kill-flag journal -- the new event type marks kill
    enforcement only, never generic denials."""
    revoked = _lease(worker_run_id=RUN, status="REVOKED")
    broker, _registry, _provider, events, _handles, _ledger = _service([revoked])
    with pytest.raises(DdeError):
        await broker.issue(
            tenant_id=TENANT,
            project_id=PROJECT,
            lease_id=revoked.lease_id,
            requested_by="test",
            idempotency_key="issue:no-kill-journal",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert events.appended == []


async def test_revoke_handles_for_leases_kills_only_that_runs_live_handles() -> None:
    """TASK B, handle half of the stop: `revoke_handles_for_leases`
    revokes every still-ISSUED handle bound to the given leases through
    the broker's existing REVOKED transition -- and nothing else. The
    other run's handle stays live and its secret keeps verifying; the
    stopped run's secret stops verifying immediately."""
    killed_handle = _handle(worker_run_id=RUN)
    survivor_lease_id = uuid4()
    survivor = _handle(worker_run_id=OTHER_RUN)
    survivor_data = survivor.model_dump()
    survivor_data.update(handle_id=uuid4(), lease_id=survivor_lease_id)
    survivor = CredentialHandle.model_validate(survivor_data)
    leases = [
        _lease(worker_run_id=RUN),
        _lease(worker_run_id=OTHER_RUN, lease_id=survivor_lease_id),
    ]
    broker, registry, _provider, events, handles, _ledger = _service(leases)
    handles.handles.extend([killed_handle, survivor])
    registry.arm(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)

    revoked_handles = await broker.revoke_handles_for_leases(
        tenant_id=TENANT,
        project_id=PROJECT,
        lease_ids=[LEASE_ID],
        reason=KILL_FLAG_REASON,
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert [item.handle_id for item in revoked_handles] == [killed_handle.handle_id]
    statuses = {item.handle_id: item.status for item in handles.handles}
    assert statuses[killed_handle.handle_id] == "REVOKED"
    assert statuses[survivor.handle_id] == "ISSUED"

    per_handle_events = [
        e for e in events.appended if e["event_type"] == "CredentialRevoked"
    ]
    assert len(per_handle_events) == 1

    assert (
        await broker.verify(
            tenant_id=TENANT,
            project_id=PROJECT,
            handle_id=killed_handle.handle_id,
            secret_value=FIXTURE_SECRET,
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
        is False
    )
    assert (
        await broker.verify(
            tenant_id=TENANT,
            project_id=PROJECT,
            handle_id=survivor.handle_id,
            secret_value=FIXTURE_SECRET,
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
        is True
    )


async def test_revoke_handles_for_leases_skips_non_live_rows() -> None:
    """Idempotent re-arm behaviour: already-SUPERSEDED/EXPIRED/REVOKED
    rows contribute nothing and raise nothing -- only live material is
    transitioned."""
    superseded = _handle(worker_run_id=RUN)
    data = superseded.model_dump()
    data.update(status="SUPERSEDED", superseded_by_handle_id=uuid4())
    superseded = CredentialHandle.model_validate(data)
    broker, _registry, _provider, events, handles, _ledger = _service(
        [_lease(worker_run_id=RUN)]
    )
    handles.handles.append(superseded)

    revoked = await broker.revoke_handles_for_leases(
        tenant_id=TENANT,
        project_id=PROJECT,
        lease_ids=[LEASE_ID],
        reason=KILL_FLAG_REASON,
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert revoked == []
    assert all(event["event_type"] != "CredentialRevoked" for event in events.appended)


async def test_cold_restart_broker_refuses_admission_from_durable_record() -> None:
    """The broker half of the restart scenario: a stop is armed with the
    DURABLE record only (a previous process's `arm_run_stop` -- replayed
    here through `record_run_stop` against a SHARED fake ledger), then a
    brand-new broker is constructed with an empty registry. Its
    `issue()` must still refuse with KILL_FLAG_ACTIVE and derive no
    material, from the durable row alone."""
    lease = _lease(worker_run_id=RUN)
    shared_ledger = FakeCommandLedger()
    await record_run_stop(
        shared_ledger,
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        armed=True,
        reason=KILL_FLAG_REASON,
        uow=FakeUOW(),  # type: ignore[arg-type]
    )

    provider = RecordingProvider()
    events = RecordingEvents()
    cold_registry = KillSwitchRegistry()
    fresh_broker = CredentialBrokerService(
        engine=None,  # type: ignore[arg-type]
        repository=FakeHandleRepository(),
        lease_repository=FakeLeaseRepository([lease]),
        events=events,  # type: ignore[arg-type]
        commands=shared_ledger,  # type: ignore[arg-type]
        provider=provider,
        kill_switch=cold_registry,  # fresh process: nothing in memory
    )
    assert (
        cold_registry.is_killed(tenant_id=TENANT, project_id=PROJECT, worker_run_id=RUN)
        is False
    )

    with pytest.raises(DdeError) as excinfo:
        await fresh_broker.issue(
            tenant_id=TENANT,
            project_id=PROJECT,
            lease_id=LEASE_ID,
            requested_by="test",
            idempotency_key="issue:cold-restart",
            uow=FakeUOW(),  # type: ignore[arg-type]
        )
    assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"
    assert excinfo.value.details is not None
    assert excinfo.value.details["worker_run_id"] == str(RUN)
    assert provider.issue_calls == []
    enforced = [
        e for e in events.appended if e["event_type"] == "CredentialKillFlagEnforced"
    ]
    assert len(enforced) == 1


async def test_disarmed_durable_record_lets_fresh_broker_pass_again() -> None:
    """Disarm symmetry at admission: after the durable row is flipped to
    DISARMED (the operator undo), a fresh broker with a cold registry
    issues normally again."""
    lease = _lease(worker_run_id=RUN)
    shared_ledger = FakeCommandLedger()
    await record_run_stop(
        shared_ledger,
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        armed=True,
        reason=KILL_FLAG_REASON,
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    await record_run_stop(
        shared_ledger,
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        armed=False,
        reason="disarmed",
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    key = (TENANT, run_stop_idempotency_key(RUN))
    assert shared_ledger.rows[key].result == {
        "state": STOP_STATE_DISARMED,
        "reason": "disarmed",
    }
    stopped = await read_durable_run_stop(
        shared_ledger,
        tenant_id=TENANT,
        project_id=PROJECT,
        worker_run_id=RUN,
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert stopped is False

    provider = RecordingProvider()
    fresh_broker = CredentialBrokerService(
        engine=None,  # type: ignore[arg-type]
        repository=FakeHandleRepository(),
        lease_repository=FakeLeaseRepository([lease]),
        events=RecordingEvents(),  # type: ignore[arg-type]
        commands=shared_ledger,  # type: ignore[arg-type]
        provider=provider,
        kill_switch=KillSwitchRegistry(),
    )
    issued = await fresh_broker.issue(
        tenant_id=TENANT,
        project_id=PROJECT,
        lease_id=LEASE_ID,
        requested_by="test",
        idempotency_key="issue:post-disarm-restart",
        uow=FakeUOW(),  # type: ignore[arg-type]
    )
    assert issued.secret_value is not None
    assert len(provider.issue_calls) == 1
