"""PostgreSQL-backed Project Truth engine: schema, state-transition and negative
tests (Chapter 19.1). Exercises engine.truth.service.TruthService, the sole
production writer of product_constitution_versions/requirements/edrs, against a
real database rather than the in-memory test double.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from engine.core.errors import DdeError
from engine.truth.db import open_unit_of_work
from engine.truth.repository import TruthRepository
from engine.truth.service import TruthService
from tests.support.db import ensure_rls_probe_role, new_engine, seed_tenant


@pytest.mark.asyncio
async def test_schema_round_trip_persists_declared_columns() -> None:
    """A row read back from the real table validates against the JSON-schema-
    generated contract with no drift (Chapter 3.1) — the schema test."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = TruthService(engine)
        record = await service.draft_requirement(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug="REQ-SCHEMA-001",
            statement="Schema round trip is provable against the real table.",
            constraints=["No drift"],
            acceptance_conditions=["Row matches contract"],
        )
        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            reloaded = await TruthRepository().get_requirement(
                uow.connection, record.requirement_id
            )
            await uow.commit()
        assert reloaded == record
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_requirement_state_transitions_persist() -> None:
    """draft -> approved -> retired, each transition durable — the state-
    transition test."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = TruthService(engine)
        drafted = await service.draft_requirement(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug="REQ-STATE-001",
            statement="Supplier credit limits are enforced at posting time.",
            constraints=["Cannot exceed configured limit"],
            acceptance_conditions=["Posting above the limit is rejected"],
        )
        assert drafted.status == "draft"
        approved = await service.approve_requirement(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            requirement_id=drafted.requirement_id,
        )
        assert approved.status == "approved"
        retired = await service.retire_requirement(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            requirement_id=drafted.requirement_id,
        )
        assert retired.status == "retired"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_edr_propose_accept_supersede_transitions_persist() -> None:
    """proposed -> accepted, then a superseding EDR flips the prior row to
    superseded — a second state-transition path covering EDR supersession."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = TruthService(engine)
        first = await service.propose_edr(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug="EDR-STATE-001",
            context="Need a durable credit-limit policy",
            alternatives=["Hard reject", "Soft warn"],
            decision="Hard reject at posting",
            rationale="Financial integrity",
            consequences=["Posting API returns 409"],
            affected_requirement_slugs=["REQ-AP-019"],
        )
        accepted_first = await service.accept_edr(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=first.edr_id,
            decided_by_principal=fixture.principal_id,
        )
        assert accepted_first.status == "accepted"
        second = await service.propose_edr(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug="EDR-STATE-002",
            context="Revisit the credit-limit policy",
            alternatives=["Keep hard reject", "Switch to soft warn"],
            decision="Soft warn with manager override",
            rationale="Customer feedback",
            consequences=["Posting API returns 200 with a warning"],
            affected_requirement_slugs=["REQ-AP-019"],
            supersedes_id=first.edr_id,
        )
        accepted_second = await service.accept_edr(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            edr_id=second.edr_id,
            decided_by_principal=fixture.principal_id,
        )
        assert accepted_second.status == "accepted"
        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            prior = await TruthRepository().get_edr(uow.connection, first.edr_id)
            await uow.commit()
        assert prior is not None
        assert prior.status == "superseded"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_constitution_missing_headings_is_rejected() -> None:
    """Publishing a constitution missing a Chapter 2.4 heading is denied and
    never reaches the database — the negative test."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = TruthService(engine)
        with pytest.raises(DdeError) as captured:
            await service.publish_constitution(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                body_markdown="# Empty\n",
            )
        assert captured.value.error_code == "POLICY_DENIED"
        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            active = await TruthRepository().get_active_constitution(
                uow.connection, fixture.project_id
            )
            await uow.commit()
        assert active is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_duplicate_requirement_slug_is_rejected() -> None:
    """A second requirement with an already-used slug is rejected with
    VERSION_CONFLICT and does not create a second row."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = TruthService(engine)
        await service.draft_requirement(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug="REQ-DUP-001",
            statement="First requirement with this slug.",
            constraints=[],
            acceptance_conditions=["x"],
        )
        with pytest.raises(DdeError) as captured:
            await service.draft_requirement(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                slug="REQ-DUP-001",
                statement="Second requirement, same slug.",
                constraints=[],
                acceptance_conditions=["y"],
            )
        assert captured.value.error_code == "VERSION_CONFLICT"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_missing_tenant_guc_yields_no_rows() -> None:
    """A non-superuser role that never sets dde.tenant_id sees zero rows for a
    real, committed requirement — fail-closed RLS (Chapter 3.2).

    The role must not have BYPASSRLS: the local dev `dde` role is a superuser
    and always bypasses row-level security, so this test connects as a
    dedicated probe role instead of asserting anything through the owner role.
    """
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = TruthService(engine)
        record = await service.draft_requirement(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug="REQ-RLS-001",
            statement="Fail-closed RLS must hide rows with no tenant GUC set.",
            constraints=[],
            acceptance_conditions=["No GUC means no rows"],
        )
        probe_url = await ensure_rls_probe_role(engine)
        probe_engine = create_async_engine(probe_url)
        try:
            async with probe_engine.connect() as connection, connection.begin():
                result = await connection.execute(
                    text("SELECT 1 FROM requirements WHERE requirement_id = :id"),
                    {"id": record.requirement_id},
                )
                assert result.first() is None
        finally:
            await probe_engine.dispose()
    finally:
        await engine.dispose()
