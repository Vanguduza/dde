"""Recovery: a fresh engine/session against the same database sees Project
Truth rows a prior session committed (Chapter 19.1 recovery test; Chapter 3.5
durability). Uses a second AsyncEngine end to end rather than sharing any
in-process object with the writer, so this proves durability rather than
in-memory-dict visibility.
"""

from __future__ import annotations

import pytest

from engine.truth.db import open_unit_of_work
from engine.truth.repository import TruthRepository
from engine.truth.service import TruthService
from tests.support.db import new_engine, seed_tenant


@pytest.mark.asyncio
async def test_second_session_reads_committed_requirement() -> None:
    writer_engine = new_engine()
    fixture = await seed_tenant(writer_engine)
    written = await TruthService(writer_engine).draft_requirement(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        slug="REQ-RECOVERY-001",
        statement="Durable writes survive process restart.",
        constraints=[],
        acceptance_conditions=["A second process reads the same row"],
    )
    await writer_engine.dispose()  # simulate the writing process exiting

    reader_engine = new_engine()  # a fresh engine/session, as a new process would open
    try:
        async with open_unit_of_work(
            reader_engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            reread = await TruthRepository().get_requirement(
                uow.connection, written.requirement_id
            )
            await uow.commit()
        assert reread is not None
        assert reread.requirement_id == written.requirement_id
        assert reread.status == "draft"
        assert reread.statement == written.statement
    finally:
        await reader_engine.dispose()


@pytest.mark.asyncio
async def test_second_session_sees_edr_acceptance_and_constitution() -> None:
    writer_engine = new_engine()
    fixture = await seed_tenant(writer_engine)
    service = TruthService(writer_engine)
    proposed = await service.propose_edr(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        slug="EDR-RECOVERY-001",
        context="Need a durable decision store.",
        alternatives=["In-memory only", "PostgreSQL"],
        decision="PostgreSQL",
        rationale="Durability across process restarts.",
        consequences=["Writes go through one transaction"],
        affected_requirement_slugs=[],
    )
    await service.accept_edr(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        edr_id=proposed.edr_id,
        decided_by_principal=fixture.principal_id,
    )
    published = await service.publish_constitution(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        body_markdown=(
            "# Product Constitution\n\n"
            "## Purpose\nRecovery test fixture.\n\n"
            "## Target users\nDDE engineers.\n\n"
            "## Non-negotiable constraints\nDurability.\n\n"
            "## Core workflows\nMission to evidence.\n\n"
            "## UX principles\nAttention is scarce.\n\n"
            "## Security principles\nNo ambient credentials.\n\n"
            "## Architecture principles\nOne schema source of truth.\n\n"
            "## Explicit exclusions\nNo agent framework for core state.\n\n"
            "## Governance rules\nAccepted EDRs are superseded, never rewritten.\n"
        ),
    )
    await writer_engine.dispose()

    reader_engine = new_engine()
    try:
        repository = TruthRepository()
        async with open_unit_of_work(
            reader_engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            reread_edr = await repository.get_edr(uow.connection, proposed.edr_id)
            reread_constitution = await repository.get_active_constitution(
                uow.connection, fixture.project_id
            )
            await uow.commit()
        assert reread_edr is not None
        assert reread_edr.status == "accepted"
        assert reread_edr.decided_by_principal == fixture.principal_id
        assert reread_constitution is not None
        assert reread_constitution.version_id == published.version_id
        assert reread_constitution.status == "active"
    finally:
        await reader_engine.dispose()
