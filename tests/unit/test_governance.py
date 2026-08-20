"""Governance decision recording against real PostgreSQL (Chapter 13.3.5,
19.1): "a decision, once made, becomes an EDR." Exercises
`engine.governance.records.GovernanceRecords`, which composes
`TruthService.accept_edr`/`reject_edr` with `AuditService.append` and
`EventService.append` in one transaction, rather than a second, parallel
EDR, audit or event writer.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from engine.audit.service import AuditService
from engine.audit.tables import audit_events
from engine.core.errors import DdeError
from engine.events.repository import EventsRepository
from engine.events.service import EventService
from engine.events.tables import outbox
from engine.governance.records import GovernanceRecords
from engine.truth.db import open_unit_of_work
from engine.truth.service import TruthService
from tests.support.db import new_engine, seed_tenant


async def _outbox_rows_for_event(engine, fixture, event_id) -> list[dict[str, object]]:
    async with open_unit_of_work(
        engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
    ) as uow:
        result = await uow.connection.execute(
            select(outbox).where(outbox.c.event_id == event_id)
        )
        rows = [dict(row) for row in result.mappings().all()]
        await uow.commit()
    return rows


async def _propose(service: TruthService, fixture, slug: str = "EDR-GOV-001"):
    return await service.propose_edr(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        slug=slug,
        context="Need a durable credit-limit policy",
        alternatives=["Hard reject", "Soft warn"],
        decision="Hard reject at posting",
        rationale="Financial integrity",
        consequences=["Posting API returns 409"],
        affected_requirement_slugs=["REQ-AP-019"],
    )


async def _audit_rows_for(engine, fixture, event_type: str) -> list[dict[str, object]]:
    # The local dev `dde` role is a superuser and bypasses RLS (see
    # tests/support/db.py), so this filters by tenant_id explicitly rather
    # than relying on the `dde.tenant_id` GUC to scope results.
    async with open_unit_of_work(
        engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
    ) as uow:
        result = await uow.connection.execute(
            select(audit_events)
            .where(
                audit_events.c.tenant_id == fixture.tenant_id,
                audit_events.c.event_type == event_type,
            )
            .order_by(audit_events.c.sequence.asc())
        )
        rows = [dict(row) for row in result.mappings().all()]
        await uow.commit()
    return rows


@pytest.mark.asyncio
async def test_accept_decision_persists_edr_and_audit_event_together() -> None:
    """The state-transition test: accepting a decision durably flips the EDR
    to `accepted` and appends exactly one audit entry, in the same
    transaction (Chapter 3.5)."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        truth = TruthService(engine)
        audit = AuditService(engine)
        events = EventService(engine)
        governance = GovernanceRecords(engine, truth, audit, events)
        proposed = await _propose(truth, fixture)

        accepted = await governance.accept_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
            decided_by_principal=fixture.principal_id,
        )
        assert accepted.status == "accepted"

        rows = await _audit_rows_for(engine, fixture, "edr.accepted")
        assert len(rows) == 1
        assert rows[0]["payload"]["edr_id"] == str(accepted.edr_id)
        assert rows[0]["payload"]["slug"] == accepted.slug
        assert rows[0]["sequence"] == 1
        assert rows[0]["prev_hash"] is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_accept_decision_is_idempotent_without_double_auditing() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        truth = TruthService(engine)
        audit = AuditService(engine)
        events = EventService(engine)
        governance = GovernanceRecords(engine, truth, audit, events)
        proposed = await _propose(truth, fixture, slug="EDR-GOV-002")

        first = await governance.accept_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
            decided_by_principal=fixture.principal_id,
        )
        second = await governance.accept_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
            decided_by_principal=fixture.principal_id,
        )
        assert second.edr_id == first.edr_id
        assert second.status == "accepted"

        rows = await _audit_rows_for(engine, fixture, "edr.accepted")
        assert len(rows) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reject_decision_persists_edr_and_audit_event_together() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        truth = TruthService(engine)
        audit = AuditService(engine)
        events = EventService(engine)
        governance = GovernanceRecords(engine, truth, audit, events)
        proposed = await _propose(truth, fixture, slug="EDR-GOV-003")

        rejected = await governance.reject_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
            decided_by_principal=fixture.principal_id,
        )
        assert rejected.status == "rejected"

        rows = await _audit_rows_for(engine, fixture, "edr.rejected")
        assert len(rows) == 1
        assert rows[0]["payload"]["edr_id"] == str(rejected.edr_id)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_second_audit_entry_chains_to_the_first() -> None:
    """Two decisions in the same tenant chain their audit entries
    (`prev_hash` links to the prior `entry_hash`), and the chain verifies."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        truth = TruthService(engine)
        audit = AuditService(engine)
        events = EventService(engine)
        governance = GovernanceRecords(engine, truth, audit, events)
        first_edr = await _propose(truth, fixture, slug="EDR-GOV-004")
        second_edr = await _propose(truth, fixture, slug="EDR-GOV-005")

        await governance.accept_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=first_edr.edr_id,
            decided_by_principal=fixture.principal_id,
        )
        await governance.reject_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=second_edr.edr_id,
            decided_by_principal=fixture.principal_id,
        )

        accepted_rows = await _audit_rows_for(engine, fixture, "edr.accepted")
        rejected_rows = await _audit_rows_for(engine, fixture, "edr.rejected")
        assert accepted_rows[0]["sequence"] == 1
        assert rejected_rows[0]["sequence"] == 2
        assert rejected_rows[0]["prev_hash"] == accepted_rows[0]["entry_hash"]

        await audit.verify_chain(tenant_id=fixture.tenant_id)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_accept_decision_appends_event_and_pending_outbox_row_together() -> None:
    """Chapter 3.9's "Event ... Owning aggregate transaction ... Outbox"
    rule: accepting a decision appends both an `events` row and a pending
    `outbox` row in the same transaction as the EDR status change."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        truth = TruthService(engine)
        audit = AuditService(engine)
        events = EventService(engine)
        governance = GovernanceRecords(engine, truth, audit, events)
        proposed = await _propose(truth, fixture, slug="EDR-GOV-006")

        accepted = await governance.accept_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
            decided_by_principal=fixture.principal_id,
        )

        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            recorded = await EventsRepository().list_events_for_aggregate(
                uow.connection, "edr", accepted.edr_id
            )
            await uow.commit()
        assert len(recorded) == 1
        assert recorded[0].event_type == "EdrAccepted"
        assert recorded[0].payload["edr_id"] == str(accepted.edr_id)

        outbox_rows = await _outbox_rows_for_event(
            engine, fixture, recorded[0].event_id
        )
        assert len(outbox_rows) == 1
        assert outbox_rows[0]["status"] == "pending"
        assert outbox_rows[0]["published_at"] is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_accepting_a_superseding_edr_emits_superseded_event_for_prior() -> None:
    """An accept that supersedes a prior accepted EDR (Chapter 3.8) emits an
    `EdrSuperseded` event for the prior EDR, in addition to `EdrAccepted`
    for the new one."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        truth = TruthService(engine)
        audit = AuditService(engine)
        events = EventService(engine)
        governance = GovernanceRecords(engine, truth, audit, events)
        first = await _propose(truth, fixture, slug="EDR-GOV-007")
        await governance.accept_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=first.edr_id,
            decided_by_principal=fixture.principal_id,
        )
        second = await truth.propose_edr(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug="EDR-GOV-008",
            context="Revised credit-limit policy",
            alternatives=["Keep hard reject", "Switch to soft warn"],
            decision="Soft warn at posting",
            rationale="Customer feedback",
            consequences=["Posting API returns 200 with a warning header"],
            affected_requirement_slugs=["REQ-AP-019"],
            supersedes_id=first.edr_id,
        )

        accepted_second = await governance.accept_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=second.edr_id,
            decided_by_principal=fixture.principal_id,
        )
        assert accepted_second.status == "accepted"

        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            first_edr_events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "edr", first.edr_id
            )
            await uow.commit()
        # sequence 1 is `first`'s own EdrAccepted; sequence 2 is the
        # EdrSuperseded emitted when `second` supersedes it.
        assert [item.event_type for item in first_edr_events] == [
            "EdrAccepted",
            "EdrSuperseded",
        ]
        assert first_edr_events[1].payload["superseded_by"] == str(second.edr_id)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_repeated_idempotency_key_does_not_re_execute_accept_decision() -> None:
    """Negative test (Chapter 12.5, 19.1): a second `accept_decision` call
    with the same `idempotency_key` never re-executes the EDR mutation or
    the audit append — it returns the first call's stored result."""

    class _CountingAuditService(AuditService):
        def __init__(self, engine) -> None:
            super().__init__(engine)
            self.calls = 0

        async def append(self, **kwargs: object) -> object:  # type: ignore[override]
            self.calls += 1
            return await super().append(**kwargs)  # type: ignore[arg-type]

    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        truth = TruthService(engine)
        audit = _CountingAuditService(engine)
        events = EventService(engine)
        governance = GovernanceRecords(engine, truth, audit, events)
        proposed = await _propose(truth, fixture, slug="EDR-GOV-009")

        first = await governance.accept_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
            decided_by_principal=fixture.principal_id,
            idempotency_key="accept-edr-gov-009",
        )
        second = await governance.accept_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
            decided_by_principal=fixture.principal_id,
            idempotency_key="accept-edr-gov-009",
        )

        assert audit.calls == 1
        assert second.edr_id == first.edr_id
        assert second.decided_at == first.decided_at
        assert second.status == "accepted"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_idempotency_key_reused_with_different_request_conflicts() -> None:
    """A key reused for a materially different logical command (a different
    EDR) is refused outright rather than silently proceeding."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        truth = TruthService(engine)
        audit = AuditService(engine)
        events = EventService(engine)
        governance = GovernanceRecords(engine, truth, audit, events)
        first_edr = await _propose(truth, fixture, slug="EDR-GOV-010")
        second_edr = await _propose(truth, fixture, slug="EDR-GOV-011")

        await governance.accept_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=first_edr.edr_id,
            decided_by_principal=fixture.principal_id,
            idempotency_key="shared-key",
        )
        with pytest.raises(DdeError) as captured:
            await governance.accept_decision(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                edr_id=second_edr.edr_id,
                decided_by_principal=fixture.principal_id,
                idempotency_key="shared-key",
            )
        assert captured.value.error_code == "VERSION_CONFLICT"
    finally:
        await engine.dispose()
