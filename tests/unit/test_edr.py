"""EDR engine against real PostgreSQL (Chapter 19.1): the propose -> reject
path DDE-003's Postgres suite did not yet cover, and the decision-content
immutability guarantee (Chapter 2.2 rank 4) for `TruthService`, the sole
writer of the `edrs` table.

`propose -> accept -> supersede` is already exercised against Postgres by
`tests/unit/test_truth_postgres.py::test_edr_propose_accept_supersede_transitions_persist`
and is intentionally not duplicated here.
"""

from __future__ import annotations

import pytest

from engine.core.errors import DdeError
from engine.truth.service import TruthService
from tests.support.db import new_engine, seed_tenant


async def _propose(service: TruthService, fixture, slug: str = "EDR-NEG-001"):
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


@pytest.mark.asyncio
async def test_edr_propose_reject_transition_persists() -> None:
    """The state-transition test for the path DDE-003's Postgres suite left
    untested: proposed -> rejected, durable in the real table."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = TruthService(engine)
        proposed = await _propose(service, fixture, slug="EDR-REJECT-001")
        rejected = await service.reject_edr(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
            decided_by_principal=fixture.principal_id,
        )
        assert rejected.status == "rejected"
        assert rejected.decided_by_principal == fixture.principal_id
        reread = await service.get_edr(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
        )
        assert reread.status == "rejected"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_rejected_edr_cannot_then_be_accepted() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = TruthService(engine)
        proposed = await _propose(service, fixture, slug="EDR-REJECT-002")
        await service.reject_edr(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
            decided_by_principal=fixture.principal_id,
        )
        with pytest.raises(DdeError) as captured:
            await service.accept_edr(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                edr_id=proposed.edr_id,
                decided_by_principal=fixture.principal_id,
            )
        assert captured.value.error_code == "VERSION_CONFLICT"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_revise_proposed_edr_decision_succeeds() -> None:
    """A not-yet-decided EDR's content may be corrected."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = TruthService(engine)
        proposed = await _propose(service, fixture, slug="EDR-REVISE-001")
        revised = await service.revise_edr_decision(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
            decision="Soft warn with manager override",
        )
        assert revised.status == "proposed"
        assert revised.decision == "Soft warn with manager override"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_accepted_edr_decision_cannot_be_mutated() -> None:
    """The negative test: once an EDR is accepted, an attempt to mutate its
    decision content is rejected outright and the row is left unchanged —
    accepted EDRs are superseded, never rewritten (Chapter 2.2 rank 4)."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = TruthService(engine)
        proposed = await _propose(service, fixture, slug="EDR-REVISE-002")
        await service.accept_edr(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
            decided_by_principal=fixture.principal_id,
        )
        with pytest.raises(DdeError) as captured:
            await service.revise_edr_decision(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                edr_id=proposed.edr_id,
                decision="changed my mind after the fact",
            )
        assert captured.value.error_code == "POLICY_DENIED"
        unchanged = await service.get_edr(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=proposed.edr_id,
        )
        assert unchanged.decision == "Hard reject at posting"
        assert unchanged.status == "accepted"
    finally:
        await engine.dispose()
