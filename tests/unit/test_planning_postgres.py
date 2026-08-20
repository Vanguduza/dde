"""PostgreSQL-backed TaskGraph persistence: schema and negative tests
(Chapter 19.1). Exercises `engine.planning.service.TaskGraphService`, the
production writer of `task_graphs`/`task_graph_edges` (Chapter 3.8),
composed with `engine.missions.service.MissionService` under one shared
transaction (Chapter 3.5) exactly as a caller of `MissionService` sees it —
`MissionService.create_task_graph` is the entry point; `TaskGraphService`
itself is exercised directly here for reads/activation, since Chapter 3.8
assigns `task_graphs`/`task_graph_edges` to `engine.planning` alone.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from engine.contracts.graph_amendment import GraphAmendment
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
from engine.planning.validate import validate_graph
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine, seed_tenant

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
async def test_task_graph_with_tasks_and_edges_persists() -> None:
    """Creating a TaskGraph persists its `task_graphs` row
    (`engine.planning`), Task nodes (`engine.missions`) and
    `task_graph_edges` rows (`engine.planning`) together, tenant/project/
    mission-scoped, and its `graph_hash` matches the same canonical hash
    `TaskPlanner` computes in-memory (Chapter 4.2). Activation and edge
    reads go through `TaskGraphService` directly, proving it — not
    `MissionService` — is the table's production writer."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        task_graphs = TaskGraphService(engine)
        service = MissionService(engine, EventService(engine), task_graphs=task_graphs)
        mission = await _create_mission(service, fixture, slug="MISSION-GRAPH-001")

        graph_id = uuid7()
        planned = add_endpoint_template(mission, graph_id, SystemClock())
        digest = graph_hash(planned.tasks, planned.edges)

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
        assert graph.status == "APPROVED"
        assert graph.graph_hash == digest
        # DRAFT(1) -> VALIDATING(2) -> APPROVED(3): three real column
        # writes against the same row (Chapter 4.8), not an in-memory
        # shortcut straight to a terminal status.
        assert graph.lock_version == 3

        activated = await task_graphs.activate_task_graph(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            graph_id=graph_id,
            lock_version=graph.lock_version,
        )
        assert activated.status == "ACTIVE"

        persisted_tasks = await service.list_tasks_for_graph(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            graph_id=graph_id,
        )
        persisted_edges = await task_graphs.list_edges_for_graph(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            graph_id=graph_id,
        )
        assert len(persisted_tasks) == len(planned.tasks)
        assert len(persisted_edges) == len(planned.edges)
        assert {task.task_id for task in persisted_tasks} == {
            task.task_id for task in planned.tasks
        }
        assert all(task.mission_id == mission.mission_id for task in persisted_tasks)
        assert all(task.status == "CREATED" for task in persisted_tasks)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_cyclic_graph_is_persisted_as_rejected() -> None:
    """A graph containing a cycle fails `validate_graph` and is persisted
    as `REJECTED` — a real, queryable terminal status (Chapter 4.8:
    "DRAFT|VALIDATING -> REJECTED") — rather than raising and vanishing.
    Chapter 4.2's "the graph is acyclic ... enforced in the database and by
    contract test" invariant holds because no `Task`/`TaskGraphEdge` row is
    ever written for it, not because the `task_graphs` row itself is
    withheld."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = MissionService(engine, EventService(engine))
        mission = await _create_mission(service, fixture, slug="MISSION-NEG-003")
        graph_id = uuid7()
        now = datetime.now(UTC)

        def node(task_id, refs: list[str]) -> Task:
            return Task(
                task_id=task_id,
                tenant_id=mission.tenant_id,
                project_id=mission.project_id,
                mission_id=mission.mission_id,
                graph_id=graph_id,
                title="n",
                intent="i",
                task_class="implementation",
                requirement_refs=refs,
                feature_refs=[],
                success_criteria=["c"],
                expected_write_scope=["engine/core"],
                expected_read_scope=[],
                blast_radius="local",
                risk_class="low",
                estimated_effort="s",
                autonomy_ceiling=2,
                requires_approval=False,
                status="CREATED",
                lock_version=1,
                created_at=now,
                updated_at=now,
            )

        def edge(source, dest) -> TaskGraphEdge:
            return TaskGraphEdge(
                edge_id=uuid7(),
                tenant_id=mission.tenant_id,
                project_id=mission.project_id,
                mission_id=mission.mission_id,
                graph_id=graph_id,
                from_task_id=source,
                to_task_id=dest,
                edge_type="depends_on",
                created_at=now,
                updated_at=now,
            )

        left_id, right_id = uuid7(), uuid7()
        tasks = [node(left_id, [REQUIREMENT_SLUG]), node(right_id, [REQUIREMENT_SLUG])]
        edges = [edge(left_id, right_id), edge(right_id, left_id)]
        # Confirm the pure validator (the same one TaskPlanner.validate()
        # calls in-memory) already rejects this graph.
        assert validate_graph(tasks, edges).valid is False

        graph = await service.create_task_graph(
            mission=mission,
            graph_id=graph_id,
            tasks=tasks,
            edges=edges,
            planning_mode="template",
            planner_policy_version=PLANNER_POLICY_VERSION,
            rationale="cyclic",
            created_by_principal=fixture.principal_id,
            approved_requirement_slugs={REQUIREMENT_SLUG},
        )
        assert graph.status == "REJECTED"
        # DRAFT(1) -> VALIDATING(2) -> REJECTED(3): three real column
        # writes against the same row, not an in-memory shortcut.
        assert graph.lock_version == 3

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
        assert persisted_graph is not None
        assert persisted_graph.status == "REJECTED"
        assert persisted_tasks == []
        assert persisted_edges == []
    finally:
        await engine.dispose()


async def _active_graph_fixture(engine, *, slug: str):
    """Common setup for amendment tests: a mission with an ACTIVE,
    template-mode TaskGraph (spec -> impl -> verify)."""
    fixture = await seed_tenant(engine)
    task_graphs = TaskGraphService(engine)
    service = MissionService(engine, EventService(engine), task_graphs=task_graphs)
    mission = await _create_mission(service, fixture, slug=slug)
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
    return fixture, service, task_graphs, mission, active, planned


def _verification_task(mission, graph_id: UUID, *, title: str) -> Task:
    now = datetime.now(UTC)
    return Task(
        task_id=uuid7(),
        tenant_id=mission.tenant_id,
        project_id=mission.project_id,
        mission_id=mission.mission_id,
        graph_id=graph_id,
        title=title,
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


@pytest.mark.asyncio
async def test_add_task_amendment_is_auto_accepted_and_versioned() -> None:
    """Chapter 4.5 rule 2: an `add_task` amendment within scope and below
    the autonomy ceiling is auto-accepted — no human required. Accepting it
    produces `version + 1` with `supersedes_id` linking back to the amended
    graph (rule 4), inserts the new `Task` row, retires the prior version
    to `SUPERSEDED` and activates the new one, all atomically."""
    engine = new_engine()
    try:
        (
            fixture,
            service,
            task_graphs,
            mission,
            active,
            planned,
        ) = await _active_graph_fixture(engine, slug="MISSION-AMEND-ADD-TASK")
        new_graph_id = uuid7()
        new_task = _verification_task(
            mission, new_graph_id, title="Verify discovered edge case"
        )
        amendment = GraphAmendment(
            amendment_id=uuid7(),
            graph_id=active.graph_id,
            proposed_by="worker-run-1",
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

        assert amended.status == "ACTIVE"
        assert amended.version == active.version + 1
        assert amended.supersedes_id == active.graph_id

        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            planning_repo = TaskGraphRepository()
            missions_repo = MissionsRepository()
            prior = await planning_repo.get_task_graph(uow.connection, active.graph_id)
            new_tasks = await missions_repo.list_tasks_for_graph(
                uow.connection, new_graph_id
            )
            events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "task_graph", new_graph_id
            )
            await uow.commit()
        assert prior is not None
        assert prior.status == "SUPERSEDED"
        assert {task.task_id for task in new_tasks} == {new_task.task_id}
        assert [item.event_type for item in events] == ["TaskGraphAmended"]
        assert events[0].payload["amendment_type"] == "add_task"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_add_edge_amendment_is_auto_accepted_and_versioned() -> None:
    """Chapter 4.5 rule 2: an `add_edge` amendment connecting two already-
    existing tasks is auto-accepted the same way `add_task` is — no new
    `Task` rows, one new `TaskGraphEdge` row under the new version."""
    engine = new_engine()
    try:
        (
            fixture,
            service,
            task_graphs,
            mission,
            active,
            planned,
        ) = await _active_graph_fixture(engine, slug="MISSION-AMEND-ADD-EDGE")
        spec = next(task for task in planned.tasks if task.title.startswith("Specify"))
        verify = next(task for task in planned.tasks if task.title.startswith("Verify"))
        now = datetime.now(UTC)
        new_edge = TaskGraphEdge(
            edge_id=uuid7(),
            tenant_id=mission.tenant_id,
            project_id=mission.project_id,
            mission_id=mission.mission_id,
            graph_id=uuid7(),  # overwritten below to match new_graph_id
            from_task_id=spec.task_id,
            to_task_id=verify.task_id,
            edge_type="depends_on",
            created_at=now,
            updated_at=now,
        )
        new_graph_id = uuid7()
        new_edge = new_edge.model_copy(update={"graph_id": new_graph_id})
        amendment = GraphAmendment(
            amendment_id=uuid7(),
            graph_id=active.graph_id,
            proposed_by="worker-run-2",
            amendment_type="add_edge",
            justification="Spec must also gate verification directly",
            evidence_refs=[],
            affected_task_ids=[spec.task_id, verify.task_id],
            requested_write_scope=[],
        )

        amended = await service.amend_task_graph(
            mission=mission,
            amendment=amendment,
            new_graph_id=new_graph_id,
            new_tasks=[],
            new_edges=[new_edge],
            planner_policy_version=PLANNER_POLICY_VERSION,
            created_by_principal=fixture.principal_id,
            approved_requirement_slugs={REQUIREMENT_SLUG},
        )

        assert amended.status == "ACTIVE"
        assert amended.version == active.version + 1
        assert amended.supersedes_id == active.graph_id

        new_edges = await task_graphs.list_edges_for_graph(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            graph_id=new_graph_id,
        )
        assert {edge.edge_id for edge in new_edges} == {new_edge.edge_id}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_widen_scope_amendment_is_refused() -> None:
    """Chapter 4.5 rule 3: `widen_scope` requires human approval that does
    not exist yet in this vertical slice, so it must be refused outright —
    not silently auto-accepted, and not persisted as a REJECTED version
    either: nothing is written at all."""
    engine = new_engine()
    try:
        (
            fixture,
            service,
            task_graphs,
            mission,
            active,
            planned,
        ) = await _active_graph_fixture(engine, slug="MISSION-AMEND-WIDEN")
        amendment = GraphAmendment(
            amendment_id=uuid7(),
            graph_id=active.graph_id,
            proposed_by="worker-run-3",
            amendment_type="widen_scope",
            justification="drive-by refactor outside declared scope",
            evidence_refs=[],
            affected_task_ids=[],
            requested_write_scope=["secret/other-project"],
        )
        new_graph_id = uuid7()

        with pytest.raises(DdeError) as captured:
            await service.amend_task_graph(
                mission=mission,
                amendment=amendment,
                new_graph_id=new_graph_id,
                new_tasks=[],
                new_edges=[],
                planner_policy_version=PLANNER_POLICY_VERSION,
                created_by_principal=fixture.principal_id,
                approved_requirement_slugs={REQUIREMENT_SLUG},
            )
        assert captured.value.error_code == "SCOPE_VIOLATION"

        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            planning_repo = TaskGraphRepository()
            prior = await planning_repo.get_task_graph(uow.connection, active.graph_id)
            never_created = await planning_repo.get_task_graph(
                uow.connection, new_graph_id
            )
            await uow.commit()
        assert prior is not None
        assert prior.status == "ACTIVE"  # unchanged: never entered AMENDING
        assert never_created is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_out_of_scope_add_task_amendment_is_refused() -> None:
    """An `add_task` amendment is still refused, not auto-accepted, if the
    proposed node's write scope falls outside the mission's declared
    `scope` array (Chapter 4.5 rule 3 applies to any amendment that would
    otherwise widen authority, not only ones explicitly typed
    `widen_scope`)."""
    engine = new_engine()
    try:
        (
            fixture,
            service,
            task_graphs,
            mission,
            active,
            planned,
        ) = await _active_graph_fixture(engine, slug="MISSION-AMEND-OOS")
        rogue_task = _verification_task(
            mission, active.graph_id, title="Touch unrelated project"
        ).model_copy(update={"expected_write_scope": ["secret/other-project"]})
        amendment = GraphAmendment(
            amendment_id=uuid7(),
            graph_id=active.graph_id,
            proposed_by="worker-run-4",
            amendment_type="add_task",
            justification="drive-by change",
            evidence_refs=[],
            affected_task_ids=[],
            requested_write_scope=["secret/other-project"],
        )
        new_graph_id = uuid7()

        with pytest.raises(DdeError) as captured:
            await service.amend_task_graph(
                mission=mission,
                amendment=amendment,
                new_graph_id=new_graph_id,
                new_tasks=[rogue_task],
                new_edges=[],
                planner_policy_version=PLANNER_POLICY_VERSION,
                created_by_principal=fixture.principal_id,
                approved_requirement_slugs={REQUIREMENT_SLUG},
            )
        assert captured.value.error_code == "SCOPE_VIOLATION"
    finally:
        await engine.dispose()
