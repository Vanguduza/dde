"""PostgreSQL-backed Chapter 4.3 registry tests: template registry
lifecycle, untrusted-draft validation and promotion (Chapter 19.1
negative tests over the real writer, `engine.planning.registry.
PlanningRegistryService`).

Pins:
- register/retire lifecycle with typed refusals on every illegal move;
- registration idempotency on the content-hashed template_version;
- submit -> validate -> promote happy path with provenance recorded;
- every typed refusal site: empty draft, unknown origin, promoting a
  PROPOSED draft, promoting a REJECTED draft, dangling edge endpoints,
  structural validator refusals recorded on the row;
- CommandLedger replay idempotency for both mutating entry points.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from engine.contracts.plan_draft import PlanDraft
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.missions.service import MissionService
from engine.planning.registry import (
    DRAFT_VALIDATOR_POLICY_VERSION,
    DraftNotPromotableError,
    PlanningRegistryService,
    TemplateShapeError,
)
from engine.planning.service import TaskGraphService
from tests.support.db import new_engine, seed_tenant

REQUIREMENT_SLUG = "REQ-HEALTH"


def _now() -> datetime:
    return datetime.now(UTC)


def _template_nodes() -> list[dict[str, object]]:
    return [
        {
            "node_key": "spec",
            "title": "Specify endpoint contract",
            "intent": "Commit the HTTP contract first",
            "task_class": "specification",
            "write_scope": ["schemas/api"],
            "read_scope": [],
            "success_criteria": ["Endpoint schema committed"],
            "estimated_effort": "s",
        },
        {
            "node_key": "impl",
            "title": "Implement endpoint",
            "intent": "Implement the contracted handler",
            "task_class": "implementation",
            "write_scope": ["engine/gateway"],
            "read_scope": ["schemas/api"],
            "success_criteria": ["Handler returns contracted payload"],
            "estimated_effort": "s",
        },
        {
            "node_key": "verify",
            "title": "Verify endpoint",
            "intent": "Prove the contract holds",
            "task_class": "verification",
            "write_scope": ["tests"],
            "read_scope": ["engine/gateway"],
            "success_criteria": ["Contract tests pass"],
            "estimated_effort": "s",
        },
    ]


def _template_edges() -> list[dict[str, object]]:
    return [
        {"from_node_key": "spec", "to_node_key": "impl", "edge_type": "depends_on"},
        {"from_node_key": "impl", "to_node_key": "verify", "edge_type": "verifies"},
    ]


def _draft_nodes() -> list[dict[str, object]]:
    return [
        {
            "node_key": "d_spec",
            "title": "Specify endpoint contract",
            "intent": "Commit the HTTP contract first",
            "task_class": "specification",
            "requirement_refs": [REQUIREMENT_SLUG],
            "write_scope": ["schemas/api"],
            "success_criteria": ["Endpoint schema committed"],
        },
        {
            "node_key": "d_impl",
            "title": "Implement endpoint",
            "intent": "Implement the contracted handler",
            "task_class": "implementation",
            "requirement_refs": [REQUIREMENT_SLUG],
            "write_scope": ["engine/gateway"],
            "success_criteria": ["Handler returns contracted payload"],
        },
        {
            "node_key": "d_verify",
            "title": "Verify endpoint",
            "intent": "Prove the contract holds",
            "task_class": "verification",
            "requirement_refs": [REQUIREMENT_SLUG],
            "write_scope": ["tests/unit"],
            "success_criteria": ["Contract test covers the endpoint"],
        },
    ]


def _draft_edges() -> list[dict[str, object]]:
    return [
        {
            "from_node_key": "d_spec",
            "to_node_key": "d_impl",
            "edge_type": "depends_on",
        },
        {
            "from_node_key": "d_impl",
            "to_node_key": "d_verify",
            "edge_type": "depends_on",
        },
        {
            "from_node_key": "d_verify",
            "to_node_key": "d_impl",
            "edge_type": "verifies",
        },
    ]


@pytest.fixture
async def engine():
    eng = new_engine()
    yield eng
    await eng.dispose()


@pytest.fixture
def registry(engine):
    return PlanningRegistryService(engine)


@pytest.fixture
async def mission_service(engine):
    return MissionService(engine, EventService(engine))


@pytest.fixture
async def task_graphs(engine):
    return TaskGraphService(engine)


async def _create_mission(service: MissionService, fixture) -> object:
    return await service.create_mission(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        slug=f"MISSION-{uuid7().hex[:8]}",
        title="Health endpoint",
        intent="Add a /health endpoint",
        success_definition="healthz returns ok",
        scope=["engine", "schemas", "tests"],
        requirement_refs=[REQUIREMENT_SLUG],
        autonomy_ceiling=3,
    )


# --- template registry ------------------------------------------------------


@pytest.mark.asyncio
async def test_register_and_get_template_roundtrip(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    template = await registry.register_template(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        template_key="add_endpoint",
        description="Specify -> implement -> verify",
        nodes=_template_nodes(),
        edges=_template_edges(),
        created_by="principal-1",
    )
    fetched = await registry.get_template(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        template_id=template.template_id,
    )
    assert fetched is not None
    assert fetched.template_key == "add_endpoint"
    assert fetched.status == "ACTIVE"
    assert len(fetched.nodes) == 3
    assert len(fetched.edges) == 2


@pytest.mark.asyncio
async def test_register_same_definition_is_idempotent(registry, engine) -> None:
    """Chapter 3.10: identical definition fields hash to one version; a
    second registration returns the FIRST row rather than minting a twin."""
    fixture = await seed_tenant(engine)
    first = await registry.register_template(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        template_key="add_endpoint",
        description="Specify -> implement -> verify",
        nodes=_template_nodes(),
        edges=_template_edges(),
        created_by="principal-1",
    )
    second = await registry.register_template(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        template_key="add_endpoint",
        description="Specify -> implement -> verify",
        nodes=_template_nodes(),
        edges=_template_edges(),
        created_by="principal-2",
    )
    assert second.template_id == first.template_id


@pytest.mark.asyncio
async def test_material_change_mints_new_version(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    kwargs: dict[str, object] = {
        "tenant_id": fixture.tenant_id,
        "project_id": fixture.project_id,
        "template_key": "add_endpoint",
        "description": "Specify -> implement -> verify",
        "nodes": _template_nodes(),
        "edges": _template_edges(),
    }
    first = await registry.register_template(created_by="p1", **kwargs)  # type: ignore[arg-type]
    changed_nodes = _template_nodes()
    changed_nodes[0]["title"] = "Specify endpoint contract precisely"
    second = await registry.register_template(
        created_by="p1",  # type: ignore[arg-type]
        nodes=changed_nodes,  # type: ignore[arg-type]
        edges=_template_edges(),  # type: ignore[arg-type]
        description="Specify -> implement -> verify",
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        template_key="add_endpoint",
    )
    assert second.template_id != first.template_id
    assert second.template_version != first.template_version


@pytest.mark.asyncio
async def test_retire_is_terminal(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    template = await registry.register_template(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        template_key="add_endpoint",
        description="d",
        nodes=_template_nodes(),
        edges=_template_edges(),
        created_by="principal-1",
    )
    retired = await registry.retire_template(template)
    assert retired.status == "RETIRED"
    with pytest.raises(DdeError) as err:
        await registry.retire_template(retired)
    assert err.value.error_code == "VERSION_CONFLICT"
    active = await registry.list_active_templates(
        tenant_id=fixture.tenant_id, project_id=fixture.project_id
    )
    assert all(item.template_id != template.template_id for item in active)


@pytest.mark.asyncio
async def test_register_refuses_cyclic_decomposition(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    cyclic_edges: list[dict[str, object]] = [
        {"from_node_key": "spec", "to_node_key": "impl", "edge_type": "depends_on"},
        {"from_node_key": "impl", "to_node_key": "spec", "edge_type": "depends_on"},
    ]
    with pytest.raises(TemplateShapeError) as err:
        await registry.register_template(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            template_key="cyclic",
            description="d",
            nodes=_template_nodes(),
            edges=cyclic_edges,
            created_by="principal-1",
        )
    assert err.value.error_code == "GRAPH_INVALID"


@pytest.mark.asyncio
async def test_register_refuses_dangling_edge(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    dangling: list[dict[str, object]] = [
        {"from_node_key": "spec", "to_node_key": "ghost", "edge_type": "depends_on"}
    ]
    with pytest.raises(TemplateShapeError):
        await registry.register_template(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            template_key="dangling",
            description="d",
            nodes=_template_nodes(),
            edges=dangling,
            created_by="principal-1",
        )


@pytest.mark.asyncio
async def test_register_refuses_empty_node_set(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    with pytest.raises(TemplateShapeError) as err:
        await registry.register_template(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            template_key="empty",
            description="d",
            nodes=[],
            edges=[],
            created_by="principal-1",
        )
    assert err.value.error_code == "DECOMPOSITION_REQUIRED"


@pytest.mark.asyncio
async def test_register_refuses_blank_key(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    with pytest.raises(DdeError) as err:
        await registry.register_template(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            template_key="",
            description="d",
            nodes=_template_nodes(),
            edges=_template_edges(),
            created_by="principal-1",
        )
    assert err.value.error_code == "POLICY_DENIED"


# --- plan drafts --------------------------------------------------------------


async def _submit_valid_draft(
    registry: PlanningRegistryService, fixture, mission
) -> PlanDraft:
    return await registry.submit_draft(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        mission_id=mission.mission_id,
        origin="model_assisted",
        origin_policy_version=DRAFT_VALIDATOR_POLICY_VERSION,
        nodes=_draft_nodes(),
        edges=_draft_edges(),
        created_by_principal=fixture.principal_id,
        adapter_ref=None,
    )


@pytest.mark.asyncio
async def test_submit_records_untrusted_proposed_draft(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    service = MissionService(engine, EventService(engine))
    mission = await _create_mission(service, fixture)
    draft = await _submit_valid_draft(registry, fixture, mission)
    assert draft.status == "PROPOSED"
    assert draft.refusals == []
    assert len(draft.provenance_key) == 64
    assert draft.origin == "model_assisted"


@pytest.mark.asyncio
async def test_submit_replays_on_identical_proposal(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    service = MissionService(engine, EventService(engine))
    mission = await _create_mission(service, fixture)
    first = await _submit_valid_draft(registry, fixture, mission)
    second = await _submit_valid_draft(registry, fixture, mission)
    assert second.draft_id == first.draft_id


@pytest.mark.asyncio
async def test_submit_refuses_unknown_origin(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    service = MissionService(engine, EventService(engine))
    mission = await _create_mission(service, fixture)
    with pytest.raises(DdeError) as err:
        await registry.submit_draft(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            origin="template",
            origin_policy_version=DRAFT_VALIDATOR_POLICY_VERSION,
            nodes=_draft_nodes(),
            edges=_draft_edges(),
            created_by_principal=fixture.principal_id,
        )
    assert err.value.error_code == "POLICY_DENIED"


@pytest.mark.asyncio
async def test_submit_refuses_empty_decomposition(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    service = MissionService(engine, EventService(engine))
    mission = await _create_mission(service, fixture)
    with pytest.raises(DdeError) as err:
        await registry.submit_draft(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            origin="model_assisted",
            origin_policy_version=DRAFT_VALIDATOR_POLICY_VERSION,
            nodes=[],
            edges=[],
            created_by_principal=fixture.principal_id,
        )
    assert err.value.error_code == "GRAPH_INVALID"


@pytest.mark.asyncio
async def test_validate_records_verdict_and_refusals(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    service = MissionService(engine, EventService(engine))
    mission = await _create_mission(service, fixture)
    draft = await _submit_valid_draft(registry, fixture, mission)
    validated = await registry.validate_draft(
        draft,
        mission=mission,  # type: ignore[arg-type]
        approved_requirement_slugs={REQUIREMENT_SLUG},
        idempotency_key=f"validate-{draft.draft_id}",
    )
    assert validated.status == "VALIDATED"
    assert validated.refusals == []


@pytest.mark.asyncio
async def test_validate_rejects_cycle_with_recorded_refusals(registry, engine) -> None:
    """The deterministic validator's cycle refusal is durable evidence:
    the REJECTED row names exactly what the model got wrong."""
    fixture = await seed_tenant(engine)
    service = MissionService(engine, EventService(engine))
    mission = await _create_mission(service, fixture)
    cyclic_edges: list[dict[str, object]] = [
        {
            "from_node_key": "d_spec",
            "to_node_key": "d_impl",
            "edge_type": "depends_on",
        },
        {
            "from_node_key": "d_impl",
            "to_node_key": "d_spec",
            "edge_type": "depends_on",
        },
    ]
    draft = await registry.submit_draft(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        mission_id=mission.mission_id,
        origin="model_assisted",
        origin_policy_version=DRAFT_VALIDATOR_POLICY_VERSION,
        nodes=_draft_nodes(),
        edges=cyclic_edges,
        created_by_principal=fixture.principal_id,
    )
    rejected = await registry.validate_draft(
        draft,
        mission=mission,  # type: ignore[arg-type]
        approved_requirement_slugs={REQUIREMENT_SLUG},
        idempotency_key=f"validate-{draft.draft_id}",
    )
    assert rejected.status == "REJECTED"
    joined = " ".join(refusal.message for refusal in rejected.refusals)
    assert "cycle" in joined.lower(), rejected.refusals


@pytest.mark.asyncio
async def test_validate_records_dangling_edge_refusal(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    service = MissionService(engine, EventService(engine))
    mission = await _create_mission(service, fixture)
    dangling: list[dict[str, object]] = [
        {
            "from_node_key": "d_spec",
            "to_node_key": "ghost",
            "edge_type": "depends_on",
        }
    ]
    draft = await registry.submit_draft(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        mission_id=mission.mission_id,
        origin="model_assisted",
        origin_policy_version=DRAFT_VALIDATOR_POLICY_VERSION,
        nodes=_draft_nodes(),
        edges=dangling,
        created_by_principal=fixture.principal_id,
    )
    rejected = await registry.validate_draft(
        draft,
        mission=mission,  # type: ignore[arg-type]
        approved_requirement_slugs={REQUIREMENT_SLUG},
        idempotency_key=f"validate-{draft.draft_id}",
    )
    assert rejected.status == "REJECTED"
    joined = " ".join(refusal.message for refusal in rejected.refusals)
    assert "ghost" in joined


@pytest.mark.asyncio
async def test_promote_lands_real_graph_with_provenance(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    service = MissionService(engine, EventService(engine))
    mission = await _create_mission(service, fixture)
    draft = await _submit_valid_draft(registry, fixture, mission)
    validated = await registry.validate_draft(
        draft,
        mission=mission,  # type: ignore[arg-type]
        approved_requirement_slugs={REQUIREMENT_SLUG},
        idempotency_key=f"validate-{draft.draft_id}",
    )
    promoted, graph = await registry.promote_draft(
        validated,
        mission=mission,  # type: ignore[arg-type]
        graph_id=uuid7(),
        planner_policy_version=DRAFT_VALIDATOR_POLICY_VERSION,
        created_by_principal=fixture.principal_id,
        approved_requirement_slugs={REQUIREMENT_SLUG},
        create_task_graph=service.create_task_graph,
        idempotency_key=f"promote-{draft.draft_id}",
    )
    assert promoted.status == "PROMOTED"
    assert promoted.promoted_graph_id == graph.graph_id
    assert graph.planning_mode == "model_assisted"

    tasks = await service.list_tasks_for_graph(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        graph_id=graph.graph_id,
    )
    assert len(tasks) == 3
    assert all(task.status == "CREATED" for task in tasks)

    reread = await registry.get_draft(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        draft_id=draft.draft_id,
    )
    assert reread.promoted_graph_id == graph.graph_id


@pytest.mark.asyncio
async def test_promote_refuses_proposed_draft(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    service = MissionService(engine, EventService(engine))
    mission = await _create_mission(service, fixture)
    draft = await _submit_valid_draft(registry, fixture, mission)

    with pytest.raises(DraftNotPromotableError) as err:
        await registry.promote_draft(
            draft,
            mission=mission,  # type: ignore[arg-type]
            graph_id=uuid7(),
            planner_policy_version=DRAFT_VALIDATOR_POLICY_VERSION,
            created_by_principal=fixture.principal_id,
            approved_requirement_slugs={REQUIREMENT_SLUG},
            create_task_graph=service.create_task_graph,
            idempotency_key=f"promote-{draft.draft_id}",
        )
    assert err.value.error_code == "POLICY_DENIED"


@pytest.mark.asyncio
async def test_promote_refuses_rejected_draft(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    service = MissionService(engine, EventService(engine))
    mission = await _create_mission(service, fixture)
    cyclic_edges: list[dict[str, object]] = [
        {
            "from_node_key": "d_spec",
            "to_node_key": "d_impl",
            "edge_type": "depends_on",
        },
        {
            "from_node_key": "d_impl",
            "to_node_key": "d_spec",
            "edge_type": "depends_on",
        },
    ]
    draft = await registry.submit_draft(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        mission_id=mission.mission_id,
        origin="model_assisted",
        origin_policy_version=DRAFT_VALIDATOR_POLICY_VERSION,
        nodes=_draft_nodes(),
        edges=cyclic_edges,
        created_by_principal=fixture.principal_id,
    )
    rejected = await registry.validate_draft(
        draft,
        mission=mission,  # type: ignore[arg-type]
        approved_requirement_slugs={REQUIREMENT_SLUG},
        idempotency_key=f"validate-{draft.draft_id}",
    )

    with pytest.raises(DraftNotPromotableError) as err:
        await registry.promote_draft(
            rejected,
            mission=mission,  # type: ignore[arg-type]
            graph_id=uuid7(),
            planner_policy_version=DRAFT_VALIDATOR_POLICY_VERSION,
            created_by_principal=fixture.principal_id,
            approved_requirement_slugs={REQUIREMENT_SLUG},
            create_task_graph=service.create_task_graph,
            idempotency_key=f"promote-{draft.draft_id}",
        )
    assert err.value.error_code == "POLICY_DENIED"
    # And nothing was minted behind the refusal.


@pytest.mark.asyncio
async def test_validate_replay_returns_first_verdict(registry, engine) -> None:
    fixture = await seed_tenant(engine)
    service = MissionService(engine, EventService(engine))
    mission = await _create_mission(service, fixture)
    draft = await _submit_valid_draft(registry, fixture, mission)
    key = f"validate-replay-{draft.draft_id}"
    first = await registry.validate_draft(
        draft,
        mission=mission,  # type: ignore[arg-type]
        approved_requirement_slugs={REQUIREMENT_SLUG},
        idempotency_key=key,
    )
    second = await registry.validate_draft(
        first,
        mission=mission,  # type: ignore[arg-type]
        approved_requirement_slugs={REQUIREMENT_SLUG},
        idempotency_key=key,
    )
    assert second.draft_id == first.draft_id
    assert second.status == first.status


@pytest.mark.asyncio
async def test_promote_replay_returns_stored_row_without_second_graph(
    registry, engine
) -> None:
    """Recovery-style idempotency (Chapter 12.5): replaying the promote
    command returns the stored draft and the SAME promoted graph -- no
    second graph, no duplicate Task rows. A genuinely new command (new
    key) after a REJECTED draft is refused honestly rather than
    resurrected."""
    fixture = await seed_tenant(engine)
    service = MissionService(engine, EventService(engine))
    mission = await _create_mission(service, fixture)
    draft = await _submit_valid_draft(registry, fixture, mission)
    validated = await registry.validate_draft(
        draft,
        mission=mission,  # type: ignore[arg-type]
        approved_requirement_slugs={REQUIREMENT_SLUG},
        idempotency_key=f"validate-{draft.draft_id}",
    )
    first, graph = await registry.promote_draft(
        validated,
        mission=mission,  # type: ignore[arg-type]
        graph_id=uuid7(),
        planner_policy_version=DRAFT_VALIDATOR_POLICY_VERSION,
        created_by_principal=fixture.principal_id,
        approved_requirement_slugs={REQUIREMENT_SLUG},
        create_task_graph=service.create_task_graph,
        idempotency_key=f"promote-{draft.draft_id}",
    )
    second, graph_again = await registry.promote_draft(
        first,
        mission=mission,  # type: ignore[arg-type]
        graph_id=uuid7(),
        planner_policy_version=DRAFT_VALIDATOR_POLICY_VERSION,
        created_by_principal=fixture.principal_id,
        approved_requirement_slugs={REQUIREMENT_SLUG},
        create_task_graph=service.create_task_graph,
        idempotency_key=f"promote-{draft.draft_id}",
    )
    assert second.draft_id == first.draft_id
    assert graph_again.graph_id == graph.graph_id

    graphs = {graph.graph_id, graph_again.graph_id}
    assert len(graphs) == 1
