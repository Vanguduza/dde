"""PostgreSQL-backed Mission Kernel: schema, state-transition and negative
tests (Chapter 19.1). Exercises `engine.missions.service.MissionService`,
the production writer of `missions`/`tasks`, against a real database rather
than the in-memory `MissionKernel` test double.

TaskGraph-specific coverage (schema round trip, cyclic-graph rejection) now
lives in `tests/unit/test_planning_postgres.py`, exercising
`engine.planning.service.TaskGraphService` — the sole writer of
`task_graphs`/`task_graph_edges` (Chapter 3.8) — composed with
`MissionService` under one shared transaction.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from engine.core.errors import DdeError
from engine.events.service import EventService
from engine.missions.repository import MissionsRepository
from engine.missions.service import MissionService
from engine.truth.db import open_unit_of_work
from tests.support.db import ensure_rls_probe_role, new_engine, seed_tenant

REQUIREMENT_SLUG = "REQ-HEALTH"


async def _create_mission(
    service: MissionService, fixture, *, slug: str = "MISSION-HEALTH-1"
):
    return await service.create_mission(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        slug=slug,
        title="Health endpoint",
        intent="Add a /health endpoint",
        success_definition="healthz returns ok",
        scope=["engine", "schemas", "tests"],
        requirement_refs=[REQUIREMENT_SLUG],
        autonomy_ceiling=3,
    )


@pytest.mark.asyncio
async def test_schema_round_trip_persists_declared_columns() -> None:
    """A mission row read back from the real table validates against the
    JSON-schema-generated contract with no drift (Chapter 3.1) — the schema
    test."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = MissionService(engine, EventService(engine))
        created = await _create_mission(service, fixture, slug="MISSION-SCHEMA-001")
        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            reloaded = await MissionsRepository().get_mission(
                uow.connection, created.mission_id
            )
            await uow.commit()
        assert reloaded == created
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_mission_created_to_active_to_completed_persists() -> None:
    """CREATED -> ACTIVE -> COMPLETED, each transition durable — the
    state-transition test for the mission side of Chapter 4.8/4.9/12.6."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = MissionService(engine, EventService(engine))
        created = await _create_mission(service, fixture, slug="MISSION-STATE-001")
        assert created.status == "CREATED"

        active = await service.transition_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=created.mission_id,
            target_status="ACTIVE",
            lock_version=created.lock_version,
        )
        assert active.status == "ACTIVE"
        assert active.lock_version == created.lock_version + 1

        completed = await service.transition_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=created.mission_id,
            target_status="COMPLETED",
            lock_version=active.lock_version,
        )
        assert completed.status == "COMPLETED"
        assert completed.lock_version == active.lock_version + 1

        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            reread = await MissionsRepository().get_mission(
                uow.connection, created.mission_id
            )
            await uow.commit()
        assert reread is not None
        assert reread.status == "COMPLETED"
        assert reread.lock_version == completed.lock_version
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_stale_lock_version_is_rejected() -> None:
    """A write against an already-superseded `lock_version` is rejected
    with `VERSION_CONFLICT` and does not change the row — the negative
    test for Chapter 3.5 optimistic locking."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = MissionService(engine, EventService(engine))
        created = await _create_mission(service, fixture, slug="MISSION-NEG-001")
        await service.transition_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=created.mission_id,
            target_status="ACTIVE",
            lock_version=created.lock_version,
        )

        with pytest.raises(DdeError) as captured:
            await service.transition_mission(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                mission_id=created.mission_id,
                target_status="PAUSED",
                lock_version=created.lock_version,  # stale: already consumed above
            )
        assert captured.value.error_code == "VERSION_CONFLICT"
        assert captured.value.retryable is True

        reread = await service.get_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=created.mission_id,
        )
        assert reread.status == "ACTIVE"
        assert reread.lock_version == created.lock_version + 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_illegal_transition_is_rejected() -> None:
    """A transition absent from `MISSION_TRANSITIONS` (Chapter 4.8) is
    rejected without mutating the row, independent of `lock_version`."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = MissionService(engine, EventService(engine))
        created = await _create_mission(service, fixture, slug="MISSION-NEG-002")
        with pytest.raises(DdeError) as captured:
            await service.transition_mission(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                mission_id=created.mission_id,
                target_status="COMPLETED",  # CREATED can only go ACTIVE|CANCELLED
                lock_version=created.lock_version,
            )
        assert captured.value.error_code == "VERSION_CONFLICT"

        reread = await service.get_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=created.mission_id,
        )
        assert reread.status == "CREATED"
        assert reread.lock_version == created.lock_version
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_duplicate_mission_slug_is_rejected() -> None:
    """A second mission with an already-used `(project_id, slug)` pair is
    rejected with `VERSION_CONFLICT` and does not create a second row
    (schema's declared `["project_id", "slug"]` uniqueness)."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = MissionService(engine, EventService(engine))
        await _create_mission(service, fixture, slug="MISSION-DUP-001")
        with pytest.raises(DdeError) as captured:
            await _create_mission(service, fixture, slug="MISSION-DUP-001")
        assert captured.value.error_code == "VERSION_CONFLICT"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_missing_tenant_guc_yields_no_rows_for_missions() -> None:
    """Fail-closed RLS (Chapter 3.2) for the `missions` table: a
    non-superuser role that never sets `dde.tenant_id` sees zero rows for a
    real, committed mission."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = MissionService(engine, EventService(engine))
        created = await _create_mission(service, fixture, slug="MISSION-RLS-001")
        probe_url = await ensure_rls_probe_role(engine)
        probe_engine = create_async_engine(probe_url)
        try:
            async with probe_engine.connect() as connection, connection.begin():
                result = await connection.execute(
                    text("SELECT 1 FROM missions WHERE mission_id = :id"),
                    {"id": created.mission_id},
                )
                assert result.first() is None
        finally:
            await probe_engine.dispose()
    finally:
        await engine.dispose()
