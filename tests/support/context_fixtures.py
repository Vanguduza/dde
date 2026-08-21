"""Shared PostgreSQL fixtures for `engine.context` tests (Chapter 19.1).

Builds a real `Task` row (through an APPROVED, single-node TaskGraph —
`context_packages.task_id` foreign-keys `tasks`) plus real Requirement/EDR
rows the authority retriever can resolve, and a small synthetic
working-tree directory the lexical/structural/explicit retrievers scan
instead of this live repository — keeping retrieval-dependent test
assertions independent of this repo's own evolving content.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.mission import Mission
from engine.contracts.task import Task
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.missions.service import MissionService
from engine.planning.planner import PLANNER_POLICY_VERSION
from engine.truth.service import TruthService
from tests.support.db import TenantFixture, seed_tenant

REQUIREMENT_SLUG = "REQ-CTX-1"
EDR_SLUG = "EDR-CTX-1"


@dataclass
class ContextFixture:
    tenant: TenantFixture
    mission: Mission
    task: Task


def build_fake_repo(root: Path) -> Path:
    """A tiny, fully-controlled working tree standing in for "the repo"
    (Chapter 5.2) so retrieval assertions do not depend on this project's
    own, ever-changing source content."""
    (root / "engine" / "context").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "blueprint").mkdir(parents=True, exist_ok=True)
    (root / "engine" / "context" / "hashing.py").write_text(
        '"""Assembly hashing helpers."""\n'
        "\n"
        "\n"
        "def sha256_hex(payload: str) -> str:\n"
        "    return payload\n"
        "\n"
        "\n"
        "def assembly_hash(task_id: str, tenant_id: str) -> str:\n"
        "    return sha256_hex(task_id + tenant_id)\n",
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(
        "# Rules\n\n"
        "Never pass a long-lived credential to model-generated code. "
        "RLS enforces tenant isolation on every table.\n",
        encoding="utf-8",
    )
    (root / "docs" / "blueprint" / "spec.md").write_text(
        "# Architecture\n\n"
        "Modules communicate through the context assembly hash pipeline.\n",
        encoding="utf-8",
    )
    return root


async def build_context_fixture(
    engine: AsyncEngine,
    *,
    mission_slug: str,
    task_title: str = "Assembly hash determinism",
    task_intent: str = "sha256_hex hashing tenant rls credential handling",
    success_criteria: list[str] | None = None,
    requirement_refs: list[str] | None = None,
    expected_read_scope: list[str] | None = None,
    expected_write_scope: list[str] | None = None,
    requirement_status: str = "approved",
    edr_status: str = "accepted",
    include_edr: bool = True,
    risk_class: str = "low",
    blast_radius: str = "local",
) -> ContextFixture:
    tenant = await seed_tenant(engine)
    truth = TruthService(engine)
    requirement = await truth.draft_requirement(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        slug=REQUIREMENT_SLUG,
        statement="ContextPackages hash their assembled evidence deterministically",
        constraints=["Hash excludes lifecycle columns"],
        acceptance_conditions=["Recompiling identical inputs yields the same hash"],
    )
    if requirement_status == "approved":
        requirement = await truth.approve_requirement(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            requirement_id=requirement.requirement_id,
        )

    approved_slugs = {REQUIREMENT_SLUG}
    if include_edr:
        edr = await truth.propose_edr(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            slug=EDR_SLUG,
            context="Context assembly needs a canonical, stable hash",
            alternatives=["Hash the whole row", "Hash definition fields only"],
            decision="Hash definition fields only, excluding lifecycle columns",
            rationale="Chapter 3.10: a status change must never invalidate a hash",
            consequences=["Recompiled packages with identical evidence share a hash"],
            affected_requirement_slugs=[REQUIREMENT_SLUG],
        )
        if edr_status == "accepted":
            await truth.accept_edr(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                edr_id=edr.edr_id,
                decided_by_principal=tenant.principal_id,
            )
        approved_slugs.add(EDR_SLUG)

    mission_service = MissionService(engine, EventService(engine))
    mission = await mission_service.create_mission(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        slug=mission_slug,
        title="Context compilation",
        intent="Compile ContextPackages for tasks",
        success_definition="ContextPackage rows persist with real coverage",
        scope=["engine", "docs", "AGENTS.md"],
        requirement_refs=[REQUIREMENT_SLUG],
        autonomy_ceiling=3,
    )

    refs = (
        requirement_refs
        if requirement_refs is not None
        else ([REQUIREMENT_SLUG, EDR_SLUG] if include_edr else [REQUIREMENT_SLUG])
    )
    # Planning-time approval only checks a ref against the graph's approved
    # slug set (engine/planning/validate.py), not against a live Truth row.
    # A caller-supplied ref that names no real Requirement/EDR (e.g. to
    # exercise an authority-retriever "unresolved" coverage case) must still
    # be in this set, or graph creation itself would reject the task before
    # context compilation ever runs.
    approved_slugs.update(refs)
    criteria = success_criteria or [
        "Recompiling identical inputs yields the same assembly_hash"
    ]
    read_scope = (
        expected_read_scope
        if expected_read_scope is not None
        else ["engine/context/hashing.py", "AGENTS.md"]
    )
    write_scope = (
        expected_write_scope if expected_write_scope is not None else ["engine/context"]
    )
    now = datetime.now(UTC)
    graph_id = uuid7()
    task_id = uuid7()
    task = Task(
        task_id=task_id,
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        mission_id=mission.mission_id,
        graph_id=graph_id,
        title=task_title,
        intent=task_intent,
        task_class="verification",
        requirement_refs=refs,
        feature_refs=[],
        success_criteria=criteria,
        expected_write_scope=write_scope,
        expected_read_scope=read_scope,
        blast_radius=blast_radius,  # type: ignore[arg-type]
        risk_class=risk_class,  # type: ignore[arg-type]
        estimated_effort="s",
        autonomy_ceiling=2,
        requires_approval=False,
        verification_profile_ref="unit",
        status="CREATED",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )
    graph = await mission_service.create_task_graph(
        mission=mission,
        graph_id=graph_id,
        tasks=[task],
        edges=[],
        planning_mode="template",
        planner_policy_version=PLANNER_POLICY_VERSION,
        rationale="DDE-008 context fixture",
        created_by_principal=tenant.principal_id,
        approved_requirement_slugs=approved_slugs,
    )
    assert graph.status == "APPROVED", graph
    persisted_tasks = await mission_service.list_tasks_for_graph(
        tenant_id=tenant.tenant_id, project_id=tenant.project_id, graph_id=graph_id
    )
    persisted_task = persisted_tasks[0]
    return ContextFixture(tenant=tenant, mission=mission, task=persisted_task)


async def build_conflicting_edr_context_fixture(
    engine: AsyncEngine,
    *,
    mission_slug: str,
) -> ContextFixture:
    """Two independently **accepted** EDRs naming the same requirement slug
    in `affected_requirement_slugs`, with no supersession link between
    them -- the exact `overlapping_accepted_edrs` shape Chapter 5.6 names
    (`engine.context.conflict._overlapping_accepted_edrs`). The Task's
    `requirement_refs` names both EDR slugs so the real authority
    retriever resolves both for the same `compile()` call."""
    tenant = await seed_tenant(engine)
    truth = TruthService(engine)
    requirement = await truth.draft_requirement(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        slug=REQUIREMENT_SLUG,
        statement="ContextPackages hash their assembled evidence deterministically",
        constraints=["Hash excludes lifecycle columns"],
        acceptance_conditions=["Recompiling identical inputs yields the same hash"],
    )
    requirement = await truth.approve_requirement(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        requirement_id=requirement.requirement_id,
    )

    edr_a_slug = "EDR-CTX-CONFLICT-A"
    edr_b_slug = "EDR-CTX-CONFLICT-B"
    edr_a = await truth.propose_edr(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        slug=edr_a_slug,
        context="Context assembly needs a canonical, stable hash",
        alternatives=["Hash the whole row", "Hash definition fields only"],
        decision="Hash definition fields only, excluding lifecycle columns",
        rationale="Chapter 3.10: a status change must never invalidate a hash",
        consequences=["Recompiled packages with identical evidence share a hash"],
        affected_requirement_slugs=[REQUIREMENT_SLUG],
    )
    edr_a = await truth.accept_edr(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        edr_id=edr_a.edr_id,
        decided_by_principal=tenant.principal_id,
    )
    edr_b = await truth.propose_edr(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        slug=edr_b_slug,
        context="Context assembly needs a canonical, stable hash",
        alternatives=["Hash the whole row plus a version marker"],
        decision="Hash the whole row, including lifecycle columns",
        rationale="A conflicting governance decision over the same requirement",
        consequences=["Recompiled packages with identical evidence share a hash"],
        affected_requirement_slugs=[REQUIREMENT_SLUG],
    )
    edr_b = await truth.accept_edr(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        edr_id=edr_b.edr_id,
        decided_by_principal=tenant.principal_id,
    )
    assert edr_a.status == "accepted"
    assert edr_b.status == "accepted"
    assert edr_a.supersedes_id is None
    assert edr_b.supersedes_id is None

    mission_service = MissionService(engine, EventService(engine))
    mission = await mission_service.create_mission(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        slug=mission_slug,
        title="Context compilation",
        intent="Compile ContextPackages for tasks",
        success_definition="ContextPackage rows persist with real coverage",
        scope=["engine", "docs", "AGENTS.md"],
        requirement_refs=[REQUIREMENT_SLUG],
        autonomy_ceiling=3,
    )

    refs = [edr_a_slug, edr_b_slug]
    approved_slugs = {REQUIREMENT_SLUG, edr_a_slug, edr_b_slug}
    now = datetime.now(UTC)
    graph_id = uuid7()
    task_id = uuid7()
    task = Task(
        task_id=task_id,
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        mission_id=mission.mission_id,
        graph_id=graph_id,
        title="Assembly hash determinism",
        intent="sha256_hex hashing tenant rls credential handling",
        task_class="verification",
        requirement_refs=refs,
        feature_refs=[],
        success_criteria=["Recompiling identical inputs yields the same assembly_hash"],
        expected_write_scope=["engine/context"],
        expected_read_scope=["engine/context/hashing.py", "AGENTS.md"],
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
    graph = await mission_service.create_task_graph(
        mission=mission,
        graph_id=graph_id,
        tasks=[task],
        edges=[],
        planning_mode="template",
        planner_policy_version=PLANNER_POLICY_VERSION,
        rationale="DDE-031 conflicting-EDR context fixture",
        created_by_principal=tenant.principal_id,
        approved_requirement_slugs=approved_slugs,
    )
    assert graph.status == "APPROVED", graph
    persisted_tasks = await mission_service.list_tasks_for_graph(
        tenant_id=tenant.tenant_id, project_id=tenant.project_id, graph_id=graph_id
    )
    persisted_task = persisted_tasks[0]
    return ContextFixture(tenant=tenant, mission=mission, task=persisted_task)
