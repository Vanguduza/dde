"""Shared PostgreSQL fixture for `interfaces.cli.mission_trace` tests
(Chapter 19.1): one real mission spanning every node the mission-trace
command must reconstruct -- Mission -> TaskGraph -> Task -> ContextPackage ->
RouteDecision -> ExecutionPlan -> ExecutionEnvironment -> Workspace ->
WorkerRun -> VerificationRun -> Evidence -> IntegrationProposal -- built
entirely from already-existing `tests.support.*` fixtures and real
production services (never hand-inserted rows), exactly as
`tests/support/integration_fixtures.py` composes `tests/support/
execution_fixtures.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.context.repo import repo_root
from engine.contracts.integration_proposal import IntegrationProposal
from engine.contracts.mission import Mission
from engine.contracts.route_decision import RouteDecision
from engine.integration.service import IntegrationQueueService
from tests.support.db import TenantFixture
from tests.support.execution_fixtures import build_execution_fixture
from tests.support.integration_fixtures import AdvancedTask, advance_task_to_verified


@dataclass
class TraceableMission:
    tenant: TenantFixture
    mission: Mission
    mission_id: UUID
    advanced: AdvancedTask
    proposal: IntegrationProposal
    route_decision: RouteDecision
    task_branch: str
    mission_branch: str


async def build_traceable_mission(
    engine: AsyncEngine,
    root: Path,
    *,
    mission_slug: str,
    write_path: str = "engine/routing/dde014-mission-trace.txt",
    mission_title: str = "Routing fixture mission",
    mission_intent: str = "Exercise the deterministic router end to end",
    requirement_slug: str | None = None,
    requirement_statement: str | None = None,
) -> TraceableMission:
    """A single `verification`-class task, advanced all the way through a
    real `PASSED` `VerificationRun` and a real `MERGED` `IntegrationProposal`
    -- the full spine `dde mission trace` must reconstruct, produced through
    real services exactly as `tests/support/integration_fixtures.py`'s own
    happy-path test does."""
    fixture = await build_execution_fixture(
        engine,
        root,
        mission_slug=mission_slug,
        task_class="verification",
        mission_title=mission_title,
        mission_intent=mission_intent,
        requirement_slug=requirement_slug,
        requirement_statement=requirement_statement,
    )
    advanced = await advance_task_to_verified(
        engine,
        root,
        tenant=fixture.tenant,
        task=fixture.task,
        context_package=fixture.context_package,
        route_decision=fixture.route_decision,
        write_files={write_path: b"dde-014 mission trace fixture\n"},
        idempotency_prefix=f"{mission_slug}-trace",
    )

    queue = IntegrationQueueService(engine, root=repo_root())
    proposal = await queue.submit(
        tenant_id=advanced.task.tenant_id,
        project_id=advanced.task.project_id,
        mission_id=advanced.task.mission_id,
        task_id=advanced.task.task_id,
        task_attempt_id=advanced.task_attempt_id,
        workspace=advanced.workspace,
        lease=advanced.lease,
        verification_run_id=advanced.verification_run.verification_run_id,
        attempt_label="a",
    )
    merged = await queue.integrate(proposal=proposal, workspace=advanced.workspace)

    return TraceableMission(
        tenant=fixture.tenant,
        mission=fixture.mission,
        mission_id=fixture.mission.mission_id,
        advanced=advanced,
        proposal=merged,
        route_decision=fixture.route_decision,
        task_branch=f"task/{advanced.task.task_id}-a",
        mission_branch=f"mission/{advanced.task.mission_id}",
    )
