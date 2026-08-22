"""PostgreSQL-backed `engine.capabilities.broker.service`: schema,
state-transition, negative and recovery tests (Chapter 19.1) -- DDE-019's
Credential Broker acceptance proof.

Mirrors `tests/unit/test_capability_leases_postgres.py`'s fixture shape: a
real, `GRANTED` `CapabilityLease` promoted to `ACTIVE` via `require_active`
(exactly the live state Chapter 14.3's `issue(lease)` requires), then
exercised against the real `CredentialBrokerService`.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from engine.capabilities.broker.service import CredentialBrokerService
from engine.capabilities.kill_switch import (
    ADMISSION_ENFORCEMENT_EVENT_TYPE,
    CHECKOUT_ENFORCEMENT_EVENT_TYPE,
    KILL_FLAG_REASON,
    RUN_STOP_ARMED_EVENT_TYPE,
)
from engine.capabilities.lease_service import CapabilityLeaseService
from engine.capabilities.seed import seed_capabilities
from engine.capabilities.service import CapabilityRegistryService
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.repository import EventsRepository
from engine.execution.service import ExecutionPlanService
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine
from tests.support.execution_fixtures import build_execution_fixture


async def _active_lease_fixture(engine, tmp_path: Path, *, mission_slug: str):
    execution_fixture = await build_execution_fixture(
        engine, tmp_path, mission_slug=mission_slug, task_class="verification"
    )
    await seed_capabilities(
        CapabilityRegistryService(engine),
        tenant_id=execution_fixture.tenant.tenant_id,
        project_id=execution_fixture.tenant.project_id,
    )
    plan = await ExecutionPlanService(engine).plan(
        task=execution_fixture.task,
        route_decision=execution_fixture.route_decision,
        context_package_id=execution_fixture.context_package.package_id,
    )
    leases = CapabilityLeaseService(engine)
    worker_run_id = uuid7()
    await leases.request(
        tenant_id=execution_fixture.tenant.tenant_id,
        project_id=execution_fixture.tenant.project_id,
        mission_id=execution_fixture.mission.mission_id,
        task_id=execution_fixture.task.task_id,
        execution_plan_id=plan.plan_id,
        worker_run_id=worker_run_id,
        capability_id="capability.run_local_process",
        capability_version="1",
        requested_by="system:test",
        idempotency_key=f"{worker_run_id}:capability.run_local_process",
    )
    active_lease = await leases.require_active(
        tenant_id=execution_fixture.tenant.tenant_id,
        project_id=execution_fixture.tenant.project_id,
        worker_run_id=worker_run_id,
        capability_id="capability.run_local_process",
    )
    assert active_lease.status == "ACTIVE"
    return execution_fixture, plan, leases, active_lease


@pytest.mark.asyncio
async def test_schema_round_trip_persists_declared_columns(tmp_path: Path) -> None:
    """A row read back from the real `credential_handles` table validates
    against the JSON-schema-generated contract with no drift (Chapter 3.1)
    -- the schema test."""
    engine = new_engine()
    try:
        fixture, _plan, _leases, lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-SCHEMA"
        )
        broker = CredentialBrokerService(engine)
        issued = await broker.issue(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=lease.lease_id,
            requested_by="system:test",
            idempotency_key=f"issue:{lease.lease_id}",
        )
        assert issued.handle.status == "ISSUED"
        assert issued.handle.provider_id == "local_secret"
        assert issued.secret_value is not None
        assert len(issued.secret_value) > 20
        # The digest, not the raw value, is what a real row ever carries.
        assert issued.handle.secret_hash != issued.secret_value

        reloaded = await broker.get_handle(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            handle_id=issued.handle.handle_id,
        )
        assert reloaded == issued.handle
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_issued_credential_never_outlives_its_lease(tmp_path: Path) -> None:
    """Chapter 14.3: a credential "never silently widens authority or
    extends beyond the lease" -- proven by requesting a TTL far longer than
    the lease's own remaining lifetime and observing the clamp."""
    engine = new_engine()
    try:
        fixture, _plan, _leases, lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-CLAMP"
        )
        broker = CredentialBrokerService(engine)
        issued = await broker.issue(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=lease.lease_id,
            requested_by="system:test",
            idempotency_key=f"issue-clamp:{lease.lease_id}",
            ttl=timedelta(days=999),
        )
        assert issued.handle.expires_at == lease.expires_at
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_requesting_the_same_issuance_twice_is_idempotent(tmp_path: Path) -> None:
    """A replayed `issue()` call returns the SAME durable handle record but
    never re-delivers the original secret (see
    `engine.capabilities.broker.service`'s module docstring)."""
    engine = new_engine()
    try:
        fixture, _plan, _leases, lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-IDEMPOTENT"
        )
        broker = CredentialBrokerService(engine)
        kwargs = dict(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=lease.lease_id,
            requested_by="system:test",
            idempotency_key=f"issue-idem:{lease.lease_id}",
        )
        first = await broker.issue(**kwargs)
        second = await broker.issue(**kwargs)
        assert second.handle.handle_id == first.handle.handle_id
        assert first.secret_value is not None
        assert second.secret_value is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_state_transition_renew_supersedes_the_old_handle(
    tmp_path: Path,
) -> None:
    """Chapter 14.3's `renew(lease, credential)`: issues a real replacement
    and the superseded handle's own material stops verifying."""
    engine = new_engine()
    try:
        fixture, _plan, _leases, lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-RENEW"
        )
        broker = CredentialBrokerService(engine)
        issued = await broker.issue(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=lease.lease_id,
            requested_by="system:test",
            idempotency_key=f"issue-renew:{lease.lease_id}",
        )
        assert issued.secret_value is not None

        renewed = await broker.renew(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            handle_id=issued.handle.handle_id,
            requested_by="system:test",
            idempotency_key=f"renew:{issued.handle.handle_id}",
        )
        assert renewed.handle.handle_id != issued.handle.handle_id
        assert renewed.handle.supersedes_handle_id == issued.handle.handle_id
        assert renewed.handle.status == "ISSUED"
        assert renewed.secret_value is not None
        assert renewed.secret_value != issued.secret_value

        old = await broker.get_handle(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            handle_id=issued.handle.handle_id,
        )
        assert old.status == "SUPERSEDED"
        assert old.superseded_by_handle_id == renewed.handle.handle_id

        # The old secret no longer verifies; the new one does.
        assert (
            await broker.verify(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                handle_id=issued.handle.handle_id,
                secret_value=issued.secret_value,
            )
            is False
        )
        assert (
            await broker.verify(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                handle_id=renewed.handle.handle_id,
                secret_value=renewed.secret_value,
            )
            is True
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_issue_against_a_granted_but_not_yet_active_lease_is_denied(
    tmp_path: Path,
) -> None:
    """Chapter 14.3's real lease validation gate: a `GRANTED` lease that has
    never actually been used (never promoted to `ACTIVE` via
    `require_active`) is not yet an "ACTIVE CapabilityLease" -- denied."""
    engine = new_engine()
    try:
        fixture = await build_execution_fixture(
            engine,
            tmp_path,
            mission_slug="MISSION-CRED-NEG-GRANTED",
            task_class="verification",
        )
        await seed_capabilities(
            CapabilityRegistryService(engine),
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        )
        plan = await ExecutionPlanService(engine).plan(
            task=fixture.task,
            route_decision=fixture.route_decision,
            context_package_id=fixture.context_package.package_id,
        )
        leases = CapabilityLeaseService(engine)
        worker_run_id = uuid7()
        granted = await leases.request(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            execution_plan_id=plan.plan_id,
            worker_run_id=worker_run_id,
            capability_id="capability.run_local_process",
            capability_version="1",
            requested_by="system:test",
            idempotency_key=f"{worker_run_id}:capability.run_local_process",
        )
        assert granted.status == "GRANTED"

        broker = CredentialBrokerService(engine)
        with pytest.raises(DdeError) as excinfo:
            await broker.issue(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                lease_id=granted.lease_id,
                requested_by="system:test",
                idempotency_key=f"issue-granted:{granted.lease_id}",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_issue_against_a_revoked_lease_is_denied(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        fixture, _plan, leases, lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-NEG-REVOKED"
        )
        revoked = await leases.revoke(lease=lease, reason="test revocation")
        assert revoked.status == "REVOKED"

        broker = CredentialBrokerService(engine)
        with pytest.raises(DdeError) as excinfo:
            await broker.issue(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                lease_id=lease.lease_id,
                requested_by="system:test",
                idempotency_key=f"issue-revoked:{lease.lease_id}",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_issue_against_an_unknown_lease_is_denied(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        fixture, _plan, _leases, _lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-NEG-UNKNOWN"
        )
        broker = CredentialBrokerService(engine)
        bogus_lease_id = uuid7()
        with pytest.raises(DdeError) as excinfo:
            await broker.issue(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                lease_id=bogus_lease_id,
                requested_by="system:test",
                idempotency_key=f"issue-unknown:{bogus_lease_id}",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_expired_credential_fails_verification(tmp_path: Path) -> None:
    """Chapter 14.3's own binding field "expiry" must actually gate use --
    proven with a negative TTL, mirroring
    `test_capability_leases_postgres.py`'s identical convention for a
    `CapabilityLease`'s own expiry."""
    engine = new_engine()
    try:
        fixture, _plan, _leases, lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-EXPIRED"
        )
        broker = CredentialBrokerService(engine)
        issued = await broker.issue(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=lease.lease_id,
            requested_by="system:test",
            idempotency_key=f"issue-expired:{lease.lease_id}",
            ttl=timedelta(seconds=-1),
        )
        assert issued.secret_value is not None

        assert (
            await broker.verify(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                handle_id=issued.handle.handle_id,
                secret_value=issued.secret_value,
            )
            is False
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_verify_rejects_the_wrong_secret_value(tmp_path: Path) -> None:
    engine = new_engine()
    try:
        fixture, _plan, _leases, lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-WRONG-SECRET"
        )
        broker = CredentialBrokerService(engine)
        issued = await broker.issue(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=lease.lease_id,
            requested_by="system:test",
            idempotency_key=f"issue-wrong:{lease.lease_id}",
        )
        assert (
            await broker.verify(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                handle_id=issued.handle.handle_id,
                secret_value="definitely-not-the-real-secret",  # noqa: S106 -- deliberately wrong
            )
            is False
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_revocation_cascade_denies_further_use_and_renewal(
    tmp_path: Path,
) -> None:
    """Chapter 14.3's `revoke(credential)`: "always invalidates locally" --
    proven end-to-end: the credential stops verifying, and a subsequent
    `renew()` against the now-`REVOKED` handle is denied, not silently
    handed a fresh replacement."""
    engine = new_engine()
    try:
        fixture, _plan, _leases, lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-REVOKE-CASCADE"
        )
        broker = CredentialBrokerService(engine)
        issued = await broker.issue(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=lease.lease_id,
            requested_by="system:test",
            idempotency_key=f"issue-cascade:{lease.lease_id}",
        )
        revoked = await broker.revoke(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            handle_id=issued.handle.handle_id,
            reason="operator revoked",
        )
        assert revoked.status == "REVOKED"
        assert revoked.revocation_reason == "operator revoked"

        assert (
            await broker.verify(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                handle_id=issued.handle.handle_id,
                secret_value=issued.secret_value,
            )
            is False
        )

        with pytest.raises(DdeError) as excinfo:
            await broker.renew(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                handle_id=issued.handle.handle_id,
                requested_by="system:test",
                idempotency_key=f"renew-after-revoke:{issued.handle.handle_id}",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_emergency_revoke_revokes_every_live_handle_in_the_mission_scope(
    tmp_path: Path,
) -> None:
    """Chapter 14.3's `emergency_revoke(scope)`: "Revokes all active
    material under a tenant/project/mission/run scope." Two independently
    issued handles under the same mission are both revoked by one call;
    see `CredentialBrokerService.emergency_revoke`'s own docstring for why
    "terminates dependent runs" is not implemented here."""
    engine = new_engine()
    try:
        fixture, _plan, leases, lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-EMERGENCY"
        )
        broker = CredentialBrokerService(engine)
        first = await broker.issue(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=lease.lease_id,
            requested_by="system:test",
            idempotency_key=f"issue-emergency-1:{lease.lease_id}",
        )

        # A second, independent ACTIVE lease under the SAME mission.
        worker_run_id_2 = uuid7()
        granted_2 = await leases.request(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            execution_plan_id=lease.execution_plan_id,
            worker_run_id=worker_run_id_2,
            capability_id="capability.workspace_filesystem",
            capability_version="1",
            requested_by="system:test",
            idempotency_key=f"{worker_run_id_2}:capability.workspace_filesystem",
        )
        active_2 = await leases.require_active(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=worker_run_id_2,
            capability_id="capability.workspace_filesystem",
        )
        second = await broker.issue(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=active_2.lease_id,
            requested_by="system:test",
            idempotency_key=f"issue-emergency-2:{active_2.lease_id}",
        )
        assert granted_2.status == "GRANTED"

        revoked = await broker.emergency_revoke(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            reason="mission-wide emergency revocation",
        )
        revoked_ids = {handle.handle_id for handle in revoked}
        assert first.handle.handle_id in revoked_ids
        assert second.handle.handle_id in revoked_ids
        assert all(handle.status == "REVOKED" for handle in revoked)

        for issued in (first, second):
            assert (
                await broker.verify(
                    tenant_id=fixture.tenant.tenant_id,
                    project_id=fixture.tenant.project_id,
                    handle_id=issued.handle.handle_id,
                    secret_value=issued.secret_value,
                )
                is False
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_inspect_returns_non_secret_metadata_for_a_lease(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        fixture, _plan, _leases, lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-INSPECT"
        )
        broker = CredentialBrokerService(engine)
        issued = await broker.issue(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=lease.lease_id,
            requested_by="system:test",
            idempotency_key=f"issue-inspect:{lease.lease_id}",
        )
        handles = await broker.inspect(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=lease.lease_id,
        )
        assert [handle.handle_id for handle in handles] == [issued.handle.handle_id]
        metadata = handles[0]
        assert metadata.provider_id == "local_secret"
        assert metadata.status == "ISSUED"
        assert metadata.expires_at == issued.handle.expires_at
        assert metadata.issued_by_policy_version == lease.issued_by_policy_version
        assert not hasattr(metadata, "secret_value")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_second_session_sees_the_exact_committed_credential_record(
    tmp_path: Path,
) -> None:
    """Chapter 19.1's recovery test type: a credential handle RECORD
    committed by one session (engine/connection pool) is read back
    identically by a fresh one. Deliberately does not assert on the raw
    secret value surviving anywhere -- by this mission's own design choice
    (see `engine.capabilities.broker.service`'s module docstring) it never
    was persisted, so recovery proves the record's lifecycle state, exactly
    as this mission's acceptance requires."""
    writer_engine = new_engine()
    fixture, _plan, _leases, lease = await _active_lease_fixture(
        writer_engine, tmp_path, mission_slug="MISSION-CRED-RECOVERY"
    )
    broker = CredentialBrokerService(writer_engine)
    issued = await broker.issue(
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
        lease_id=lease.lease_id,
        requested_by="system:test",
        idempotency_key=f"issue-recovery:{lease.lease_id}",
    )
    await writer_engine.dispose()

    reader_engine = new_engine()
    try:
        reader_broker = CredentialBrokerService(reader_engine)
        reloaded = await reader_broker.get_handle(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            handle_id=issued.handle.handle_id,
        )
        assert reloaded == issued.handle
        assert reloaded.secret_hash == issued.handle.secret_hash
    finally:
        await reader_engine.dispose()


@pytest.mark.asyncio
async def test_armed_checkout_refusal_journals_event_atomically(
    tmp_path: Path,
) -> None:
    """TASK A, checkout surface, against the real `events` table: the
    kill-flag refusal journals `CapabilityKillFlagEnforced` in the SAME
    transaction that revokes the run's held leases -- a fresh session
    reads the committed event back after the typed refusal."""
    engine = new_engine()
    try:
        fixture, _plan, leases, lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-KILL-JOURNAL-CHECKOUT"
        )
        leases.kill_switch.arm(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=lease.worker_run_id,
        )
        with pytest.raises(DdeError) as excinfo:
            await leases.require_active(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                worker_run_id=lease.worker_run_id,
                capability_id="capability.run_local_process",
            )
        assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "worker_run", lease.worker_run_id
            )
            await uow.commit()
        enforced = [
            event
            for event in events
            if event.event_type == (CHECKOUT_ENFORCEMENT_EVENT_TYPE)
        ]
        assert len(enforced) == 1
        assert enforced[0].payload["surface"] == "checkout"
        assert enforced[0].payload["reason"] == KILL_FLAG_REASON
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_armed_admission_refusal_journals_event_atomically(
    tmp_path: Path,
) -> None:
    """TASK A, credential-admission surface, against the real `events`
    table: an armed stop's `issue()` refusal journals
    `CredentialKillFlagEnforced` (aggregate = the lease) in the same
    committed transaction, and derives no secret material."""
    engine = new_engine()
    try:
        fixture, _plan, _leases, lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-KILL-JOURNAL-ADMISSION"
        )
        broker = CredentialBrokerService(engine)
        broker._kill_switch.arm(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=lease.worker_run_id,
        )
        with pytest.raises(DdeError) as excinfo:
            await broker.issue(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                lease_id=lease.lease_id,
                requested_by="system:test",
                idempotency_key=f"issue-killed:{lease.lease_id}",
            )
        assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "capability_lease", lease.lease_id
            )
            await uow.commit()
        enforced = [
            event
            for event in events
            if event.event_type == (ADMISSION_ENFORCEMENT_EVENT_TYPE)
        ]
        assert len(enforced) == 1
        assert enforced[0].payload["surface"] == "credential_admission"
        assert enforced[0].payload["worker_run_id"] == str(lease.worker_run_id)
        assert enforced[0].payload["capability_id"] == lease.capability_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_arm_run_stop_sweeps_leases_and_handles_in_one_transaction(
    tmp_path: Path,
) -> None:
    """TASK B end-to-end against PostgreSQL: one shared unit of work arms
    the stop -- two held leases (one ACTIVE, one GRANTED) land REVOKED
    (reason kill_flag), the live handle bound to them is revoked via the
    broker's existing transition, ONE CapabilityRunStopArmed summary
    event commits, and a subsequent require_active still refuses
    (backstop intact)."""
    engine = new_engine()
    try:
        fixture, plan, leases, first = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-KILL-SWEEP"
        )
        # A second, still-GRANTED lease for the SAME run.
        granted_2 = await leases.request(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=fixture.task.task_id,
            execution_plan_id=plan.plan_id,
            worker_run_id=first.worker_run_id,
            capability_id="capability.workspace_filesystem",
            capability_version="1",
            requested_by="system:test",
            idempotency_key=f"{first.worker_run_id}:fs",
        )
        assert granted_2.status == "GRANTED"
        broker = CredentialBrokerService(engine)
        issued = await broker.issue(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=first.lease_id,
            requested_by="system:test",
            idempotency_key=f"issue-sweep:{first.lease_id}",
        )
        secret_value = issued.secret_value

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as shared:
            revoked_leases = await leases.arm_run_stop(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                worker_run_id=first.worker_run_id,
                uow=shared,
            )
            revoked_handles = await broker.revoke_handles_for_leases(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                lease_ids=[lease.lease_id for lease in revoked_leases],
                reason=KILL_FLAG_REASON,
                uow=shared,
            )
            await shared.commit()

        assert {item.lease_id for item in revoked_leases} == {
            first.lease_id,
            granted_2.lease_id,
        }
        reloaded_first = await leases.get_lease(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=first.lease_id,
        )
        reloaded_second = await leases.get_lease(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            lease_id=granted_2.lease_id,
        )
        assert reloaded_first.status == "REVOKED"
        assert reloaded_first.revocation_reason == KILL_FLAG_REASON
        assert reloaded_second.status == "REVOKED"
        assert [handle.handle_id for handle in revoked_handles] == [
            issued.handle.handle_id
        ]
        swept = await broker.get_handle(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            handle_id=issued.handle.handle_id,
        )
        assert swept.status == "REVOKED"
        assert swept.revocation_reason == KILL_FLAG_REASON
        assert secret_value is not None
        assert (
            await broker.verify(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                handle_id=swept.handle_id,
                secret_value=secret_value,
            )
            is False
        )

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            summaries = await EventsRepository().list_events_for_aggregate(
                uow.connection, "worker_run", first.worker_run_id
            )
            per_handle = await EventsRepository().list_events_for_aggregate(
                uow.connection, "credential_handle", issued.handle.handle_id
            )
            await uow.commit()
        armed = [
            event
            for event in summaries
            if event.event_type == (RUN_STOP_ARMED_EVENT_TYPE)
        ]
        assert len(armed) == 1
        assert armed[0].payload["revoked_count"] == 2
        assert set(armed[0].payload["revoked_lease_ids"]) == {
            str(first.lease_id),
            str(granted_2.lease_id),
        }
        assert any(event.event_type == "CredentialRevoked" for event in per_handle)

        with pytest.raises(DdeError) as excinfo:
            await leases.require_active(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                worker_run_id=first.worker_run_id,
                capability_id="capability.run_local_process",
            )
        assert excinfo.value.error_code == "KILL_FLAG_ACTIVE"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_disarmed_run_journals_no_kill_flag_events(tmp_path: Path) -> None:
    """Disarmed behaviour unchanged: a run's whole lease lifecycle emits
    no kill-flag enforcement journal of either surface."""
    engine = new_engine()
    try:
        fixture, _plan, leases, lease = await _active_lease_fixture(
            engine, tmp_path, mission_slug="MISSION-CRED-DISARMED"
        )

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "worker_run", lease.worker_run_id
            )
            await uow.commit()
        assert not any(
            event.event_type
            in {
                CHECKOUT_ENFORCEMENT_EVENT_TYPE,
                ADMISSION_ENFORCEMENT_EVENT_TYPE,
                RUN_STOP_ARMED_EVENT_TYPE,
            }
            for event in events
        )
    finally:
        await engine.dispose()
