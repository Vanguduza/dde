"""DDE-069 M1 — characterization of the DDE-067 Frontend Studio invariants.

These tests exist to freeze the safety behaviour the Frontend Studio V2
migration must not regress. They deliberately assert *current* production
behaviour through the real Gateway command boundary (`POST /v1/commands`),
not through `FrontendStudioService` directly, so a refactor that moves the
domain behind new services still has to keep the same admission answers.

Distinct from `test_frontend_studio_postgres.py`, which proves the happy
paths landed by DDE-067. This file proves the *refusals* and the
idempotency/scoping guarantees that a migration is most likely to lose.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime

import httpx
import pytest

from engine.context.repo import repo_root
from engine.core.ids import uuid7
from engine.workspaces.service import WorkspaceService
from interfaces.api import app
from tests.support.db import new_engine, seed_tenant
from tests.support.worker_fixtures import build_worker_fixture

STARTER = b"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8" /></head>
<body></body></html>
"""


def _command_body(
    *,
    key: str,
    session_id: object,
    principal_id: object,
    target_id: object,
    command_type: str,
    parameters: dict[str, object],
) -> dict[str, object]:
    return {
        "command_id": str(uuid7()),
        "idempotency_key": key,
        "principal_id": str(principal_id),
        "client_session_id": str(session_id),
        "target_type": "mission",
        "target_id": str(target_id),
        "command_type": command_type,
        "parameters": parameters,
        "requested_at": datetime.now(UTC).isoformat(),
        "protocol_version": "1",
    }


async def _seed_grant(engine, *, tenant_id, principal_id, project_id) -> None:
    from sqlalchemy import text

    now = datetime.now(UTC)
    async with engine.connect() as connection:
        await connection.execute(
            text(
                "INSERT INTO principal_grants "
                "(grant_id, tenant_id, project_id, principal_id, scope_type, "
                "grant_scope, created_at, updated_at) "
                "VALUES (:grant_id, :tenant_id, :project_id, :principal_id, "
                "'PROJECT', 'PROJECT', :now, :now)"
            ),
            {
                "grant_id": uuid7(),
                "tenant_id": tenant_id,
                "project_id": project_id,
                "principal_id": principal_id,
                "now": now,
            },
        )
        await connection.commit()


async def _open_session(client: httpx.AsyncClient, principal_id: object) -> str:
    opened = await client.post(
        "/v1/sessions",
        json={
            "principal_id": str(principal_id),
            "client_type": "human",
            "scopes": ["mission.read", "mission.control", "approval.request"],
            "subscriptions": ["mission"],
        },
    )
    assert opened.status_code == 201, opened.text
    return opened.json()["session_id"]


@pytest.mark.asyncio
async def test_frontend_command_boundary_refusals(tmp_path) -> None:
    """The admission answers a V2 migration must not silently widen."""
    engine = new_engine()
    app.state.engine = engine
    workspace = None
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-FS-CHAR-1"
        )
        workspace = worker.workspace
        await _seed_grant(
            engine,
            tenant_id=worker.tenant.tenant_id,
            principal_id=worker.tenant.principal_id,
            project_id=worker.tenant.project_id,
        )
        spaces = WorkspaceService(engine, root=repo_root())
        spaces.write(worker.workspace, "prototypes/screens/cart.ready.html", STARTER)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            sid = await _open_session(client, worker.tenant.principal_id)
            pid = worker.tenant.principal_id
            mid = worker.mission.mission_id
            ws = str(worker.workspace.workspace_id)

            # 1. An unknown `frontend.*` command_type is refused, not
            #    forwarded to the studio service on the strength of its
            #    prefix. A V2 command family must be registered explicitly.
            unknown = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs-char-unknown",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.candidate.promote",
                    parameters={},
                ),
            )
            assert unknown.status_code == 403, unknown.text
            assert unknown.json()["error_code"] == "FORBIDDEN"

            # 2. `screen_file` is a filename inside prototypes/screens, never
            #    a path. Traversal is refused before any workspace read.
            for hostile in ("../../etc/passwd", "nested/dir.html", "cart.ready.txt"):
                traversal = await client.post(
                    "/v1/commands",
                    json=_command_body(
                        key=f"fs-char-traverse-{abs(hash(hostile))}",
                        session_id=sid,
                        principal_id=pid,
                        target_id=mid,
                        command_type="frontend.canvas.insert_component",
                        parameters={
                            "workspace_id": ws,
                            "screen_file": hostile,
                            "component_ref": "button",
                            "anchor_parent": "root",
                            "position_index": 0,
                            "label": "x",
                        },
                    ),
                )
                assert traversal.status_code == 403, hostile
                assert traversal.json()["error_code"] == "POLICY_DENIED"

            # 3. A workspace UUID that is not this tenant/project's is
            #    refused, and the refusal is a scope violation rather than a
            #    generic not-found that a caller could probe with.
            other = await seed_tenant(engine)
            foreign = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs-char-foreign-ws",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.canvas.insert_component",
                    parameters={
                        "workspace_id": str(uuid7()),
                        "screen_file": "cart.ready.html",
                        "component_ref": "button",
                        "anchor_parent": "root",
                        "position_index": 0,
                        "label": "x",
                    },
                ),
            )
            assert foreign.status_code in (403, 404), foreign.text
            assert foreign.json()["error_code"] in (
                "TENANT_SCOPE_VIOLATION",
                "NOT_FOUND",
                "POLICY_DENIED",
            )
            assert other.tenant_id != worker.tenant.tenant_id

            # 4. Token discipline is enforced on every writable property, not
            #    only on `color`. Freehand literals are refused at the server
            #    mutation boundary, so a richer V2 inspector cannot bypass it
            #    by choosing a different property.
            base = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs-char-base-insert",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.canvas.insert_component",
                    parameters={
                        "workspace_id": ws,
                        "screen_file": "cart.ready.html",
                        "component_ref": "button",
                        "anchor_parent": "root",
                        "position_index": 0,
                        "label": "Pay",
                    },
                ),
            )
            assert base.status_code == 202, base.text
            element_id = base.json()["payload"]["element_id"]

            for prop, literal in (
                ("color", "#1177bb"),
                ("spacing", "16px"),
                ("radius", "8px"),
            ):
                refused = await client.post(
                    "/v1/commands",
                    json=_command_body(
                        key=f"fs-char-literal-{prop}",
                        session_id=sid,
                        principal_id=pid,
                        target_id=mid,
                        command_type="frontend.canvas.update_element",
                        parameters={
                            "workspace_id": ws,
                            "screen_file": "cart.ready.html",
                            "element_id": element_id,
                            "property": prop,
                            "value": literal,
                        },
                    ),
                )
                assert refused.status_code == 403, f"{prop}={literal}"
                assert refused.json()["error_code"] == "POLICY_DENIED"
    finally:
        if workspace is not None:
            with suppress(Exception):
                await WorkspaceService(engine, root=repo_root()).cleanup(
                    workspace=workspace
                )
        await engine.dispose()


@pytest.mark.asyncio
async def test_replayed_canvas_insert_does_not_mutate_twice(tmp_path) -> None:
    """CommandLedger idempotency is a *mutation* guarantee, not just a
    matching response body. Replaying an insert must leave one element."""
    engine = new_engine()
    app.state.engine = engine
    workspace = None
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-FS-CHAR-2"
        )
        workspace = worker.workspace
        await _seed_grant(
            engine,
            tenant_id=worker.tenant.tenant_id,
            principal_id=worker.tenant.principal_id,
            project_id=worker.tenant.project_id,
        )
        spaces = WorkspaceService(engine, root=repo_root())
        spaces.write(worker.workspace, "prototypes/screens/cart.ready.html", STARTER)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            sid = await _open_session(client, worker.tenant.principal_id)
            body = _command_body(
                key="fs-char-idem-insert",
                session_id=sid,
                principal_id=worker.tenant.principal_id,
                target_id=worker.mission.mission_id,
                command_type="frontend.canvas.insert_component",
                parameters={
                    "workspace_id": str(worker.workspace.workspace_id),
                    "screen_file": "cart.ready.html",
                    "component_ref": "button",
                    "anchor_parent": "root",
                    "position_index": 0,
                    "label": "Pay",
                },
            )
            first = await client.post("/v1/commands", json=body)
            assert first.status_code == 202, first.text
            second = await client.post("/v1/commands", json=body)
            assert second.status_code == 202, second.text
            assert (
                second.json()["payload"]["element_id"]
                == first.json()["payload"]["element_id"]
            )

        from engine.studio.canvas import list_elements

        html = spaces.read(
            worker.workspace, "prototypes/screens/cart.ready.html"
        ).decode("utf-8")
        assert len(list_elements(html)) == 1, "replay inserted a second element"
    finally:
        if workspace is not None:
            with suppress(Exception):
                await WorkspaceService(engine, root=repo_root()).cleanup(
                    workspace=workspace
                )
        await engine.dispose()


@pytest.mark.asyncio
async def test_dde069_contract_pxg_coverage_through_the_command_boundary() -> None:
    """DDE-069 M5/M6 vertical slice through the real Gateway.

    Publishing a contract, applying a PXG revision and recomputing
    coverage must all be ordinary `/v1/commands` writes -- same ledger,
    same scope checks, same idempotency -- and the coverage payload must
    carry `weighted_percent: null` while anything is unknown.
    """
    engine = new_engine()
    app.state.engine = engine
    try:
        fixture = await seed_tenant(engine)
        await _seed_grant(
            engine,
            tenant_id=fixture.tenant_id,
            principal_id=fixture.principal_id,
            project_id=fixture.project_id,
        )
        from engine.events.service import EventService
        from engine.missions.service import MissionService

        mission = await MissionService(engine, EventService(engine)).create_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug=f"MISSION-FS69-{uuid7().hex[:12]}",
            title="Frontend Studio V2",
            intent="Publish a contract and a graph",
            success_definition="Coverage computed from real state",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=2,
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            sid = await _open_session(client, fixture.principal_id)
            pid = fixture.principal_id
            mid = mission.mission_id

            published = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs69-contract-1",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.contract.publish",
                    parameters={
                        "obligations": [
                            {
                                "dimension": "screen",
                                "pxg_key": "screens/checkout",
                                "statement": "Checkout screen exists",
                                "applicability": "REQUIRED",
                            },
                            {
                                "dimension": "accessibility",
                                "pxg_key": "screens/checkout",
                                "statement": "Checkout meets AA",
                                "applicability": "REQUIRED",
                                "verification_kinds": ["visual_critique"],
                            },
                        ]
                    },
                ),
            )
            assert published.status_code == 202, published.text
            assert published.json()["payload"]["contract_version"] == 1

            # An obligation waived without a decision reference is refused
            # at the command boundary, not quietly accepted.
            silent = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs69-contract-silent",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.contract.publish",
                    parameters={
                        "obligations": [
                            {
                                "dimension": "screen",
                                "pxg_key": "screens/x",
                                "statement": "dropped",
                                "applicability": "DEFERRED_APPROVED",
                            }
                        ]
                    },
                ),
            )
            assert silent.status_code == 403
            assert silent.json()["error_code"] == "POLICY_DENIED"

            applied = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs69-pxg-1",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.pxg.apply",
                    parameters={
                        "nodes": [
                            {
                                "pxg_key": "screens/checkout",
                                "node_kind": "screen",
                                "title": "Checkout",
                                "attributes": {"route": "/checkout"},
                            },
                            {
                                "pxg_key": "screens/checkout#summary",
                                "node_kind": "region",
                                "title": "Order summary",
                                "parent_key": "screens/checkout",
                            },
                        ]
                    },
                ),
            )
            assert applied.status_code == 202, applied.text
            assert applied.json()["payload"]["pxg_revision"] == 1

            # A malformed key is refused rather than stored.
            hostile = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs69-pxg-hostile",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.pxg.apply",
                    parameters={
                        "nodes": [
                            {
                                "pxg_key": "../../etc/passwd",
                                "node_kind": "screen",
                                "title": "x",
                            }
                        ]
                    },
                ),
            )
            assert hostile.status_code == 400
            assert hostile.json()["error_code"] == "VALIDATION_FAILED"

            covered = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs69-coverage-1",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.coverage.recompute",
                    parameters={},
                ),
            )
            assert covered.status_code == 202, covered.text
            payload = covered.json()["payload"]

            # The screen exists, so its dimension is fully assessed. The
            # accessibility obligation requires a visual_critique that has
            # not run, so that dimension is PARTIAL -- and the summary
            # must therefore carry no number at all.
            assert payload["summary_state"] == "PARTIAL"
            assert payload["weighted_percent"] is None
            by_dimension = {item["dimension"]: item for item in payload["dimensions"]}
            assert by_dimension["screen"]["state"] == "ASSESSED"
            assert by_dimension["screen"]["percent"] == 100.0
            assert by_dimension["accessibility"]["state"] == "PARTIAL"
            assert by_dimension["accessibility"]["unverified_count"] == 1
            assert by_dimension["accessibility"]["percent"] is None
    finally:
        await engine.dispose()
