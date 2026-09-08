"""Fresh PostgreSQL fixture for the packaged VS Code Frontend Studio E2E."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import uvicorn
from sqlalchemy import text
from tests.support.routing_fixtures import build_routing_fixture

from engine.contracts.pxg_node import SourceRef
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.gateway.app import create_app
from engine.missions.service import MissionService
from engine.studio.candidates.lifecycle import CandidateState
from engine.studio.candidates.service import CandidateService
from engine.studio.pxg.service import NodeInput, PxgService
from engine.truth.db import build_engine
from engine.workspaces.service import WorkspaceService


async def _seed() -> dict[str, str]:
    database_url = os.environ["DDE_DATABASE_URL"]
    fixture_file = Path(os.environ["DDE_PACKAGED_E2E_FIXTURE_FILE"])
    fixture_repo = Path(os.environ["DDE_PACKAGED_E2E_FIXTURE_REPO"])
    await asyncio.to_thread(fixture_repo.mkdir, parents=True, exist_ok=True)
    engine = build_engine(database_url)
    try:
        fixture = await build_routing_fixture(
            engine,
            fixture_repo,
            mission_slug=f"MISSION-PACKAGED-HOST-{uuid7().hex[:8]}",
            mission_title="Packaged Frontend Studio E2E",
            mission_intent="Prove the production VS Code host against the real Gateway",
        )
        tenant = fixture.tenant
        now = datetime.now(UTC)
        second_project_id = uuid7()
        async with engine.connect() as connection:
            await connection.execute(
                text(
                    "INSERT INTO projects "
                    "(project_id, tenant_id, slug, created_at, updated_at) "
                    "VALUES (:p, :t, :slug, :n, :n)"
                ),
                {
                    "p": second_project_id,
                    "t": tenant.tenant_id,
                    "slug": f"project-{second_project_id.hex}",
                    "n": now,
                },
            )
            for project_id in (tenant.project_id, second_project_id):
                await connection.execute(
                    text(
                        "INSERT INTO principal_grants "
                        "(grant_id, tenant_id, project_id, principal_id, "
                        "scope_type, grant_scope, created_at, updated_at) "
                        "VALUES (:g, :t, :p, :pr, 'PROJECT', 'PROJECT', :n, :n)"
                    ),
                    {
                        "g": uuid7(),
                        "t": tenant.tenant_id,
                        "p": project_id,
                        "pr": tenant.principal_id,
                        "n": now,
                    },
                )
            await connection.commit()

        mission_service = MissionService(engine, EventService(engine))
        second_mission = await mission_service.create_mission(
            tenant_id=tenant.tenant_id,
            project_id=second_project_id,
            slug=f"MISSION-PACKAGED-HOST-ALT-{uuid7().hex[:8]}",
            title="Packaged Frontend Studio E2E alternate project",
            intent="Prove project switching through the production VS Code host",
            success_definition="The workbench switches projects through the Gateway",
            scope=["interfaces/dde-studio"],
            requirement_refs=[],
            autonomy_ceiling=3,
        )
        pxg = PxgService(engine)
        await pxg.apply(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            nodes=(
                NodeInput(
                    pxg_key="screens/checkout",
                    node_kind="screen",
                    title="Checkout",
                    source_refs=(SourceRef(path="prototypes/screens/checkout.html"),),
                    attributes={"route": "/checkout"},
                ),
                NodeInput(
                    pxg_key="screens/checkout#hero",
                    node_kind="region",
                    title="Checkout hero",
                    parent_key="screens/checkout",
                    source_refs=(SourceRef(path="prototypes/screens/checkout.html"),),
                    attributes={
                        "spacing": "space2",
                        "layout_type": "stack",
                        "direction": "vertical",
                        "gap": "space2",
                        "padding": "space2",
                        "element_id": "hero",
                    },
                ),
            ),
        )
        await pxg.apply(
            tenant_id=tenant.tenant_id,
            project_id=second_project_id,
            nodes=(
                NodeInput(
                    pxg_key="screens/alternate",
                    node_kind="screen",
                    title="Alternate",
                    attributes={"route": "/alternate"},
                ),
            ),
        )

        workspaces = WorkspaceService(engine)
        candidate_workspace = await workspaces.create(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            mission_id=fixture.mission.mission_id,
            task_id=None,
            execution_environment_id=None,
            base_revision=None,
            policy={"purpose": "packaged_host_candidate_fixture"},
        )
        workspaces.write(
            candidate_workspace,
            "prototypes/screens/checkout.html",
            (
                b"<!doctype html><html><body>"
                b'<main data-dde-el="checkout">'
                b'<div data-dde-el="hero" data-dde-spacing="space2">Hero space2</div>'
                b"</main></body></html>"
            ),
        )
        candidates = CandidateService(engine)
        candidate = await candidates.create(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            mission_id=fixture.mission.mission_id,
            title="Packaged Direction A",
            origin="DIRECT_EDIT",
            scope_keys=("screens/checkout",),
        )
        for state in (CandidateState.GENERATING, CandidateState.GENERATED):
            candidate = await candidates.transition(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                candidate_id=candidate.candidate_id,
                target=state,
            )
        candidate = await candidates.transition(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            candidate_id=candidate.candidate_id,
            target=CandidateState.MATERIALIZING,
            workspace_id=candidate_workspace.workspace_id,
            detail="packaged host fixture workspace attached",
        )
        for state in (CandidateState.RENDERING, CandidateState.READY):
            candidate = await candidates.transition(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                candidate_id=candidate.candidate_id,
                target=state,
            )

        payload = {
            "tenant_id": str(tenant.tenant_id),
            "project_id": str(tenant.project_id),
            "principal_id": str(tenant.principal_id),
            "mission_id": str(fixture.mission.mission_id),
            "project_slug": f"project-{tenant.project_id.hex}",
            "principal_slug": f"principal-{tenant.principal_id.hex}",
            "screen_key": "screens/checkout",
            "screen_title": "Checkout",
            "second_project_id": str(second_project_id),
            "second_mission_id": str(second_mission.mission_id),
            "second_screen_key": "screens/alternate",
            "second_screen_title": "Alternate",
            "candidate_id": str(candidate.candidate_id),
            "candidate_workspace_id": str(candidate_workspace.workspace_id),
        }
        await asyncio.to_thread(
            fixture_file.write_text, json.dumps(payload), encoding="utf-8"
        )
        return payload
    finally:
        await engine.dispose()


async def _cleanup(payload: dict[str, str]) -> None:
    engine = build_engine(os.environ["DDE_DATABASE_URL"])
    try:
        workspace = await WorkspaceService(engine).get_workspace(
            tenant_id=UUID(payload["tenant_id"]),
            project_id=UUID(payload["project_id"]),
            workspace_id=UUID(payload["candidate_workspace_id"]),
        )
        await WorkspaceService(engine).cleanup(workspace=workspace)
        path_exists = bool(workspace.workspace_path) and await asyncio.to_thread(
            Path(workspace.workspace_path).exists
        )
        if path_exists:
            raise RuntimeError(
                f"candidate workspace cleanup left directory {workspace.workspace_path}"
            )
        print(
            f"PACKAGED_HOST_FIXTURE_CLEANUP {payload['candidate_workspace_id']}",
            flush=True,
        )
    finally:
        await engine.dispose()


def main() -> None:
    if "--cleanup-only" in sys.argv[1:]:
        fixture_file = Path(os.environ["DDE_PACKAGED_E2E_FIXTURE_FILE"])
        payload = json.loads(fixture_file.read_text(encoding="utf-8"))
        asyncio.run(_cleanup(payload))
        return

    payload = asyncio.run(_seed())
    port = int(os.environ.get("DDE_PACKAGED_E2E_GATEWAY_PORT", "8769"))
    try:
        uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")
    finally:
        # Best-effort defense in depth. The packaged-host harness performs an
        # explicit idempotent cleanup before terminating this process because
        # SIGTERM delivery is not guaranteed to unwind Uvicorn in every host.
        asyncio.run(_cleanup(payload))


if __name__ == "__main__":
    main()
