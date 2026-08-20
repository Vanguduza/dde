"""TaskGraph recovery and cross-module atomicity (Chapter 19.1, 3.5).

A mission's TaskGraph spans two writers in one transaction:
`engine.planning.service.TaskGraphService` owns `task_graphs`/
`task_graph_edges`, `engine.missions.service.MissionService` owns `tasks` —
composed under one shared unit of work exactly as
`engine.governance.records` composes `TruthService`/`AuditService`/
`EventService` (Chapter 3.5). A failure in either module's write must roll
back the other's, and a second, independent engine must see all four rows
(mission, task_graph, tasks, edges) once a TaskGraph does commit — proving
durability rather than in-memory-object visibility.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from engine.contracts.graph_amendment import GraphAmendment
from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.contracts.task_graph_edge import TaskGraphEdge
from engine.core.clock import SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.repository import EventsRepository
from engine.events.service import EventService
from engine.missions.repository import MissionsRepository
from engine.missions.service import MissionService
from engine.planning.hashing import graph_hash
from engine.planning.planner import PLANNER_POLICY_VERSION
from engine.planning.repository import TaskGraphRepository
from engine.planning.service import TaskGraphService
from engine.planning.templates import add_endpoint_template
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine, seed_tenant

REQUIREMENT_SLUG = "REQ-RECOVERY"


class _FailingTaskGraphService(TaskGraphService):
    """Simulates a crash while appending `task_graph_edges`, after the
    `task_graphs` row (this same service, earlier in the transaction) and
    the `tasks` rows (`engine.missions`, in between) have already executed
    in the same open transaction."""

    async def create_edges(self, **kwargs: Any) -> list[TaskGraphEdge]:  # type: ignore[override]
        raise DdeError("POLICY_DENIED", "forced edge failure for recovery test")


async def _create_mission(service: MissionService, fixture, *, slug: str) -> Mission:
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
async def test_edge_failure_rolls_back_task_graph_and_task_rows() -> None:
    """A failure in `engine.planning`'s `create_edges` call rolls back both
    its own already-inserted `task_graphs` row and `engine.missions`'
    already-inserted `tasks` rows from the same transaction — proof that
    the cross-module transaction is genuinely atomic, not two independently
    committed writes."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = MissionService(engine, EventService(engine))
        mission = await _create_mission(
            service, fixture, slug="MISSION-ATOMIC-PLAN-001"
        )

        failing_service = MissionService(
            engine, EventService(engine), task_graphs=_FailingTaskGraphService(engine)
        )
        graph_id = uuid7()
        planned = add_endpoint_template(mission, graph_id, SystemClock())

        with pytest.raises(DdeError):
            await failing_service.create_task_graph(
                mission=mission,
                graph_id=graph_id,
                tasks=planned.tasks,
                edges=planned.edges,
                planning_mode="template",
                planner_policy_version=PLANNER_POLICY_VERSION,
                rationale=planned.rationale,
                created_by_principal=fixture.principal_id,
                approved_requirement_slugs={REQUIREMENT_SLUG},
            )

        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            planning_repo = TaskGraphRepository()
            missions_repo = MissionsRepository()
            persisted_graph = await planning_repo.get_task_graph(
                uow.connection, graph_id
            )
            persisted_tasks = await missions_repo.list_tasks_for_graph(
                uow.connection, graph_id
            )
            persisted_edges = await planning_repo.list_edges_for_graph(
                uow.connection, graph_id
            )
            await uow.commit()
        assert persisted_graph is None
        assert persisted_tasks == []
        assert persisted_edges == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_second_session_sees_committed_mission_task_graph_and_tasks() -> None:
    """Recovery test: dispose the writer's engine, open a fresh engine (a
    new-process simulation), and confirm the committed mission, task_graph,
    task and event rows are visible and consistent — task count matches and
    `lock_version` matches the last successful write."""
    writer_engine = new_engine()
    fixture = await seed_tenant(writer_engine)
    task_graphs = TaskGraphService(writer_engine)
    service = MissionService(
        writer_engine, EventService(writer_engine), task_graphs=task_graphs
    )
    created = await _create_mission(service, fixture, slug="MISSION-RECOVERY-001")
    active = await service.transition_mission(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        mission_id=created.mission_id,
        target_status="ACTIVE",
        lock_version=created.lock_version,
    )

    graph_id = uuid7()
    planned = add_endpoint_template(active, graph_id, SystemClock())
    graph = await service.create_task_graph(
        mission=active,
        graph_id=graph_id,
        tasks=planned.tasks,
        edges=planned.edges,
        planning_mode="template",
        planner_policy_version=PLANNER_POLICY_VERSION,
        rationale=planned.rationale,
        created_by_principal=fixture.principal_id,
        approved_requirement_slugs={REQUIREMENT_SLUG},
    )
    activated_graph = await task_graphs.activate_task_graph(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        graph_id=graph_id,
        lock_version=graph.lock_version,
    )
    await writer_engine.dispose()  # simulate the writing process exiting

    reader_engine = new_engine()
    try:
        missions_repo = MissionsRepository()
        planning_repo = TaskGraphRepository()
        async with open_unit_of_work(
            reader_engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            reread_mission = await missions_repo.get_mission(
                uow.connection, created.mission_id
            )
            reread_graph = await planning_repo.get_task_graph(uow.connection, graph_id)
            reread_tasks = await missions_repo.list_tasks_for_graph(
                uow.connection, graph_id
            )
            reread_edges = await planning_repo.list_edges_for_graph(
                uow.connection, graph_id
            )
            reread_events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "mission", created.mission_id
            )
            await uow.commit()
        assert reread_mission is not None
        assert reread_mission.status == "ACTIVE"
        assert reread_mission.lock_version == active.lock_version

        assert reread_graph is not None
        assert reread_graph.status == "ACTIVE"
        assert reread_graph.lock_version == activated_graph.lock_version
        assert reread_graph.graph_hash == graph_hash(planned.tasks, planned.edges)

        assert len(reread_tasks) == len(planned.tasks)
        assert len(reread_edges) == len(planned.edges)
        assert {task.task_id for task in reread_tasks} == {
            task.task_id for task in planned.tasks
        }

        assert [item.event_type for item in reread_events] == [
            "MissionCommitted",
            "MissionTransitioned",
        ]
    finally:
        await reader_engine.dispose()


@pytest.mark.asyncio
async def test_second_session_sees_amended_graph_chain_and_event() -> None:
    """Recovery test for Chapter 4.5 amendments: dispose the writer's
    engine, open a fresh one, and confirm the versioned graph chain
    (prior version SUPERSEDED, new version ACTIVE with `supersedes_id`),
    the amendment's new `Task` row and the `TaskGraphAmended` event are all
    durably visible — not merely held in an in-process object."""
    writer_engine = new_engine()
    fixture = await seed_tenant(writer_engine)
    task_graphs = TaskGraphService(writer_engine)
    service = MissionService(
        writer_engine, EventService(writer_engine), task_graphs=task_graphs
    )
    mission = await _create_mission(service, fixture, slug="MISSION-AMEND-RECOVERY")
    graph_id = uuid7()
    planned = add_endpoint_template(mission, graph_id, SystemClock())
    graph = await service.create_task_graph(
        mission=mission,
        graph_id=graph_id,
        tasks=planned.tasks,
        edges=planned.edges,
        planning_mode="template",
        planner_policy_version=PLANNER_POLICY_VERSION,
        rationale=planned.rationale,
        created_by_principal=fixture.principal_id,
        approved_requirement_slugs={REQUIREMENT_SLUG},
    )
    active = await task_graphs.activate_task_graph(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        graph_id=graph_id,
        lock_version=graph.lock_version,
    )

    now = datetime.now(UTC)
    new_graph_id = uuid7()
    new_task = Task(
        task_id=uuid7(),
        tenant_id=mission.tenant_id,
        project_id=mission.project_id,
        mission_id=mission.mission_id,
        graph_id=new_graph_id,
        title="Verify discovered edge case",
        intent="Independently verify additional discovered behaviour",
        task_class="verification",
        requirement_refs=[REQUIREMENT_SLUG],
        feature_refs=[],
        success_criteria=["Additional regression coverage exists"],
        expected_write_scope=["tests/unit"],
        expected_read_scope=["tests/unit"],
        blast_radius="local",
        risk_class="low",
        estimated_effort="s",
        autonomy_ceiling=2,
        requires_approval=False,
        verification_profile_ref="unit",
        status="CREATED",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )
    amendment = GraphAmendment(
        amendment_id=uuid7(),
        graph_id=active.graph_id,
        proposed_by="worker-run-recovery",
        amendment_type="add_task",
        justification="Discovered an untested edge case in scope",
        evidence_refs=[],
        affected_task_ids=[],
        requested_write_scope=["tests/unit"],
    )
    amended = await service.amend_task_graph(
        mission=mission,
        amendment=amendment,
        new_graph_id=new_graph_id,
        new_tasks=[new_task],
        new_edges=[],
        planner_policy_version=PLANNER_POLICY_VERSION,
        created_by_principal=fixture.principal_id,
        approved_requirement_slugs={REQUIREMENT_SLUG},
    )
    await writer_engine.dispose()  # simulate the writing process exiting

    reader_engine = new_engine()
    try:
        missions_repo = MissionsRepository()
        planning_repo = TaskGraphRepository()
        async with open_unit_of_work(
            reader_engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            reread_prior = await planning_repo.get_task_graph(
                uow.connection, active.graph_id
            )
            reread_amended = await planning_repo.get_task_graph(
                uow.connection, new_graph_id
            )
            reread_new_tasks = await missions_repo.list_tasks_for_graph(
                uow.connection, new_graph_id
            )
            reread_events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "task_graph", new_graph_id
            )
            await uow.commit()

        assert reread_prior is not None
        assert reread_prior.status == "SUPERSEDED"

        assert reread_amended is not None
        assert reread_amended.status == "ACTIVE"
        assert reread_amended.version == active.version + 1
        assert reread_amended.supersedes_id == active.graph_id
        assert reread_amended.lock_version == amended.lock_version

        assert {task.task_id for task in reread_new_tasks} == {new_task.task_id}

        assert [item.event_type for item in reread_events] == ["TaskGraphAmended"]
        assert reread_events[0].payload["new_graph_id"] == str(new_graph_id)
    finally:
        await reader_engine.dispose()
