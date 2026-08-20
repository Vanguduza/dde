"""Governance recovery (Chapter 19.1): the decision, its audit trail and its
domain event share one PostgreSQL transaction (Chapter 3.5), so a failure
recording any of them rolls back the EDR acceptance too — there is no
window where a decision is durable without its audit trail or event, or
vice versa. A second, independent engine also sees all three rows once a
decision does commit, proving durability rather than in-memory-object
visibility.
"""

from __future__ import annotations

from typing import Any

import pytest

from engine.audit.service import AuditService
from engine.core.errors import DdeError
from engine.events.idempotency import CommandLedger
from engine.events.repository import EventsRepository
from engine.events.service import EventService
from engine.governance.records import GovernanceRecords
from engine.truth.db import open_unit_of_work
from engine.truth.repository import TruthRepository
from engine.truth.service import TruthService
from tests.support.db import new_engine, seed_tenant


class _FailingAuditService(AuditService):
    """Simulates a crash while appending the audit entry, after the EDR
    status update has already executed in the same open transaction."""

    async def append(self, **kwargs: Any) -> None:  # type: ignore[override]
        raise DdeError("POLICY_DENIED", "forced audit failure for recovery test")


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_the_edr_acceptance() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        truth = TruthService(engine)
        governance = GovernanceRecords(
            engine, truth, _FailingAuditService(engine), EventService(engine)
        )
        proposed = await truth.propose_edr(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug="EDR-RECOVERY-002",
            context="Need a durable credit-limit policy",
            alternatives=["Hard reject", "Soft warn"],
            decision="Hard reject at posting",
            rationale="Financial integrity",
            consequences=["Posting API returns 409"],
            affected_requirement_slugs=["REQ-AP-019"],
        )

        with pytest.raises(DdeError):
            await governance.accept_decision(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                edr_id=proposed.edr_id,
                decided_by_principal=fixture.principal_id,
            )

        reread = await truth.get_edr(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
        )
        assert reread.status == "proposed"
        assert reread.decided_at is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_second_session_sees_committed_decision_and_audit_entry() -> None:
    writer_engine = new_engine()
    fixture = await seed_tenant(writer_engine)
    truth = TruthService(writer_engine)
    audit = AuditService(writer_engine)
    events = EventService(writer_engine)
    governance = GovernanceRecords(writer_engine, truth, audit, events)
    proposed = await truth.propose_edr(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        slug="EDR-RECOVERY-003",
        context="Need a durable credit-limit policy",
        alternatives=["Hard reject", "Soft warn"],
        decision="Hard reject at posting",
        rationale="Financial integrity",
        consequences=["Posting API returns 409"],
        affected_requirement_slugs=["REQ-AP-019"],
    )
    accepted = await governance.accept_decision(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        edr_id=proposed.edr_id,
        decided_by_principal=fixture.principal_id,
    )
    await writer_engine.dispose()  # simulate the writing process exiting

    reader_engine = new_engine()
    try:
        async with open_unit_of_work(
            reader_engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            reread_edr = await TruthRepository().get_edr(
                uow.connection, accepted.edr_id
            )
            reread_events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "edr", accepted.edr_id
            )
            await uow.commit()
        assert reread_edr is not None
        assert reread_edr.status == "accepted"
        assert len(reread_events) == 1
        assert reread_events[0].event_type == "EdrAccepted"

        # A broken or missing chain raises; reaching the next line proves a
        # second, independent engine sees the durably committed audit entry.
        await AuditService(reader_engine).verify_chain(tenant_id=fixture.tenant_id)
    finally:
        await reader_engine.dispose()


@pytest.mark.asyncio
async def test_repeated_command_survives_writer_restart_without_re_execution() -> None:
    """Recovery test (Chapter 12.5, 19.1c): a command replayed after the
    original writer process has exited — a fresh engine, fresh
    `GovernanceRecords`, fresh `CommandLedger` — is handed back the first
    call's durable result rather than re-executing the EDR acceptance."""
    writer_engine = new_engine()
    fixture = await seed_tenant(writer_engine)
    truth = TruthService(writer_engine)
    audit = AuditService(writer_engine)
    events = EventService(writer_engine)
    governance = GovernanceRecords(writer_engine, truth, audit, events)
    proposed = await truth.propose_edr(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        slug="EDR-RECOVERY-004",
        context="Need a durable credit-limit policy",
        alternatives=["Hard reject", "Soft warn"],
        decision="Hard reject at posting",
        rationale="Financial integrity",
        consequences=["Posting API returns 409"],
        affected_requirement_slugs=["REQ-AP-019"],
    )
    first = await governance.accept_decision(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        edr_id=proposed.edr_id,
        decided_by_principal=fixture.principal_id,
        idempotency_key="accept-edr-recovery-004",
    )
    await writer_engine.dispose()  # simulate the writing process exiting

    replay_engine = new_engine()
    try:
        replay_truth = TruthService(replay_engine)
        replay_audit = AuditService(replay_engine)
        replay_events = EventService(replay_engine)
        replay_commands = CommandLedger(replay_engine)
        replay_governance = GovernanceRecords(
            replay_engine, replay_truth, replay_audit, replay_events, replay_commands
        )

        replayed = await replay_governance.accept_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
            decided_by_principal=fixture.principal_id,
            idempotency_key="accept-edr-recovery-004",
        )
        assert replayed.edr_id == first.edr_id
        assert replayed.decided_at == first.decided_at

        async with open_unit_of_work(
            replay_engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            recorded_events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "edr", proposed.edr_id
            )
            await uow.commit()
        # Exactly one EdrAccepted event exists — the replay never re-entered
        # the mutation path that would have appended a second one.
        assert len(recorded_events) == 1
    finally:
        await replay_engine.dispose()
