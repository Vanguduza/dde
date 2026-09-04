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
