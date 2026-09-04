"""DDE-069 — registering a screen writes a real, gate-consumable oracle.

The pure tests prove the policy refuses to omit a binding. This one
proves the binding actually lands: a real `AcceptanceOracle` row whose
`observable_outcomes` carry `silhouette` and `visual_critique` evidence
bindings, which is exactly the shape DDE-068 already proved is enforced
at promotion. Registration and binding happen together, so a screen
cannot exist in the graph with no oracle behind it.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.acceptance.defaults import GENERATED_SCREEN, mandatory_kinds
from engine.studio.acceptance.service import ScreenAcceptanceService
from engine.studio.pxg.service import PxgService
from engine.truth.db import open_unit_of_work
from engine.verification.checks import CheckSpec
from engine.verification.repository import AcceptanceOracleRepository
from engine.workspaces.service import WorkspaceService
from interfaces.api import app
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture


@pytest.mark.asyncio
async def test_registering_a_screen_binds_the_dde068_checks(tmp_path) -> None:
    engine = new_engine()
    workspace = None
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-FS69-BIND-1"
        )
        workspace = worker.workspace
        service = ScreenAcceptanceService(engine)

        registration = await service.register_screen(
            task=worker.task,
            screen_ref="screens/checkout",
            title="Checkout",
            preview_url="file:///tmp/checkout.html",
            route="/checkout",
        )

        assert registration.pxg_revision == 1
        assert set(registration.bound_kinds) >= set(mandatory_kinds())
        assert registration.policy_version >= 1

        # The oracle is a real row with real evidence bindings -- the
        # exact shape the promotion gate already refuses on.
        oracle = registration.oracle
        bound = {
            outcome.evidence_binding.kind for outcome in oracle.observable_outcomes
        }
        assert "silhouette" in bound
        assert "visual_critique" in bound
        assert oracle.task_id == worker.task.task_id
        assert oracle.oracle_version

        # The screen is in the graph, and it records what it was bound to
        # so the binding is inspectable rather than invisible.
        graph = await PxgService(engine).load(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
        )
        node = graph.node_by_key("screens/checkout")
        assert node is not None
        assert node.node_kind == "screen"
        assert node.attributes["route"] == "/checkout"
        assert node.attributes["acceptance_oracle_version"] == (oracle.oracle_version)
        assert set(node.attributes["bound_verification_kinds"]) >= {
            "silhouette",
            "visual_critique",
        }
        assert node.provenance["authored_by_task_id"] == str(worker.task.task_id)
    finally:
        if workspace is not None:
            with suppress(Exception):
                await WorkspaceService(engine, root=repo_root()).cleanup(
                    workspace=workspace
                )
        await engine.dispose()


@pytest.mark.asyncio
async def test_a_screen_is_not_registered_when_its_binding_is_refused(
    tmp_path,
) -> None:
    """Fail closed before any write: a refused binding must not leave a
    screen sitting in the graph with nothing gating it."""
    engine = new_engine()
    workspace = None
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-FS69-BIND-2"
        )
        workspace = worker.workspace
        service = ScreenAcceptanceService(engine)

        with pytest.raises(DdeError) as excinfo:
            await service.register_screen(
                task=worker.task,
                screen_ref="screens/unbound",
                title="Unbound",
                preview_url="file:///tmp/unbound.html",
                profile="not-a-profile",
            )
        assert excinfo.value.error_code == "VALIDATION_FAILED"

        graph = await PxgService(engine).load(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
        )
        assert graph.node_by_key("screens/unbound") is None
        assert graph.revision == 0
    finally:
        if workspace is not None:
            with suppress(Exception):
                await WorkspaceService(engine, root=repo_root()).cleanup(
                    workspace=workspace
                )
        await engine.dispose()


@pytest.mark.asyncio
async def test_extra_functional_checks_ride_alongside_the_visual_ones(
    tmp_path,
) -> None:
    engine = new_engine()
    workspace = None
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-FS69-BIND-3"
        )
        workspace = worker.workspace
        registration = await ScreenAcceptanceService(engine).register_screen(
            task=worker.task,
            screen_ref="screens/orders",
            title="Orders",
            preview_url="file:///tmp/orders.html",
            profile=GENERATED_SCREEN,
            extra_specs=(
                CheckSpec(
                    outcome_id=uuid7(),
                    statement="orders unit tests pass",
                    kind="test",
                    ref="screens/orders:test",
                    command=["pytest", "-q"],
                ),
            ),
        )
        bound = {
            outcome.evidence_binding.kind
            for outcome in registration.oracle.observable_outcomes
        }
        assert bound == {"test", "silhouette", "visual_critique"}
    finally:
        if workspace is not None:
            with suppress(Exception):
                await WorkspaceService(engine, root=repo_root()).cleanup(
                    workspace=workspace
                )
        await engine.dispose()


@pytest.mark.asyncio
async def test_register_screen_through_the_real_command_boundary(tmp_path) -> None:
    """The production call site. Registering a screen through
    `/v1/commands` must land the same bound oracle, so the guarantee holds
    for the path a real authoring surface actually uses -- not only for a
    service someone remembers to call."""
    engine = new_engine()
    app.state.engine = engine
    workspace = None
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-FS69-BIND-CMD"
        )
        workspace = worker.workspace
        now = datetime.now(UTC)
        async with engine.connect() as connection:
            await connection.execute(
                text(
                    "INSERT INTO principal_grants "
                    "(grant_id, tenant_id, project_id, principal_id, "
                    "scope_type, grant_scope, created_at, updated_at) "
                    "VALUES (:g, :t, :p, :pr, 'PROJECT', 'PROJECT', :n, :n)"
                ),
                {
                    "g": uuid7(),
                    "t": worker.tenant.tenant_id,
                    "p": worker.tenant.project_id,
                    "pr": worker.tenant.principal_id,
                    "n": now,
                },
            )
            await connection.commit()

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            opened = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(worker.tenant.principal_id),
                    "client_type": "human",
                    "scopes": ["mission.read", "mission.control"],
                    "subscriptions": ["mission"],
                },
            )
            assert opened.status_code == 201, opened.text
            session_id = opened.json()["session_id"]

            def body(key: str, parameters: dict) -> dict:
                return {
                    "command_id": str(uuid7()),
                    "idempotency_key": key,
                    "principal_id": str(worker.tenant.principal_id),
                    "client_session_id": str(session_id),
                    "target_type": "mission",
                    "target_id": str(worker.mission.mission_id),
                    "command_type": "frontend.screen.register",
                    "parameters": parameters,
                    "requested_at": datetime.now(UTC).isoformat(),
                    "protocol_version": "1",
                }

            accepted = await client.post(
                "/v1/commands",
                json=body(
                    "fs69-screen-1",
                    {
                        "task_id": str(worker.task.task_id),
                        "screen_ref": "screens/dashboard",
                        "title": "Dashboard",
                        "preview_url": "file:///tmp/dashboard.html",
                        "route": "/dashboard",
                    },
                ),
            )
            assert accepted.status_code == 202, accepted.text
            payload = accepted.json()["payload"]
            assert set(payload["bound_verification_kinds"]) >= {
                "silhouette",
                "visual_critique",
            }
            assert payload["oracle_version"]

            # A task belonging to another mission cannot be used to bind a
            # screen into this one.
            crossed = await client.post(
                "/v1/commands",
                json={
                    **body(
                        "fs69-screen-crossed",
                        {
                            "task_id": str(uuid7()),
                            "screen_ref": "screens/other",
                            "title": "Other",
                            "preview_url": "file:///tmp/other.html",
                        },
                    )
                },
            )
            assert crossed.status_code in (403, 404), crossed.text

        # The oracle really is in the database with the visual bindings.
        async with open_unit_of_work(
            engine,
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
        ) as uow:
            oracle = await AcceptanceOracleRepository().get_oracle(
                uow.connection, UUID(payload["oracle_id"])
            )
        assert oracle is not None
        assert {
            outcome.evidence_binding.kind for outcome in oracle.observable_outcomes
        } >= {"silhouette", "visual_critique"}
    finally:
        if workspace is not None:
            with suppress(Exception):
                await WorkspaceService(engine, root=repo_root()).cleanup(
                    workspace=workspace
                )
        await engine.dispose()
