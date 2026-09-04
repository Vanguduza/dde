"""DDE-069 — the governed workflow, end to end through `/v1/commands`.

Everything here goes through the real Gateway: session, ledger, scope
check, dispatcher, service. The point is not that each service works in
isolation -- the other suites prove that -- but that the *path a real
client uses* enforces the same rules, since a guarantee that only holds
when you call the service directly is not a guarantee.

The positive path and the refusal paths are proven in one run, because
the interesting property is that they share a single write path.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import text

from engine.context.repo import repo_root
from engine.core.ids import uuid7
from engine.studio.pxg.service import PxgService
from engine.workspaces.service import WorkspaceService
from interfaces.api import app
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture


async def _grant(engine, *, tenant_id, project_id, principal_id) -> None:
    now = datetime.now(UTC)
    async with engine.connect() as connection:
        await connection.execute(
            text(
                "INSERT INTO principal_grants "
                "(grant_id, tenant_id, project_id, principal_id, scope_type, "
                "grant_scope, created_at, updated_at) "
                "VALUES (:g, :t, :p, :pr, 'PROJECT', 'PROJECT', :n, :n)"
            ),
            {
                "g": uuid7(),
                "t": tenant_id,
                "p": project_id,
                "pr": principal_id,
                "n": now,
            },
        )
        await connection.commit()


@pytest.mark.asyncio
async def test_the_full_governed_frontend_workflow(tmp_path) -> None:
    engine = new_engine()
    app.state.engine = engine
    workspace = None
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-FS69-E2E"
        )
        workspace = worker.workspace
        tenant = worker.tenant
        await _grant(
            engine,
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            principal_id=tenant.principal_id,
        )
        scope = {"tenant_id": tenant.tenant_id, "project_id": tenant.project_id}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            opened = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(tenant.principal_id),
                    "client_type": "human",
                    "scopes": ["mission.read", "mission.control"],
                    "subscriptions": ["mission"],
                },
            )
            assert opened.status_code == 201, opened.text
            session_id = opened.json()["session_id"]
            counter = {"n": 0}

            async def send(command_type: str, parameters: dict) -> httpx.Response:
                counter["n"] += 1
                return await client.post(
                    "/v1/commands",
                    json={
                        "command_id": str(uuid7()),
                        "idempotency_key": f"e2e-{counter['n']}",
                        "principal_id": str(tenant.principal_id),
                        "client_session_id": str(session_id),
                        "target_type": "mission",
                        "target_id": str(worker.mission.mission_id),
                        "command_type": command_type,
                        "parameters": parameters,
                        "requested_at": datetime.now(UTC).isoformat(),
                        "protocol_version": "1",
                    },
                )

            # 1. Register a screen. Its DDE-068 bindings are attached
            #    automatically -- nobody has to remember.
            registered = await send(
                "frontend.screen.register",
                {
                    "task_id": str(worker.task.task_id),
                    "screen_ref": "screens/checkout",
                    "title": "Checkout",
                    "preview_url": "file:///tmp/checkout.html",
                    "route": "/checkout",
                },
            )
            assert registered.status_code == 202, registered.text
            assert set(registered.json()["payload"]["bound_verification_kinds"]) >= {
                "silhouette",
                "visual_critique",
            }

            # 2. Declare what the frontend owes, then compute coverage. The
            #    accessibility obligation needs a critique that has not run,
            #    so the ring must carry no number.
            published = await send(
                "frontend.contract.publish",
                {
                    "obligations": [
                        {
                            "dimension": "screen",
                            "pxg_key": "screens/checkout",
                            "statement": "Checkout exists",
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
            )
            assert published.status_code == 202, published.text

            covered = await send("frontend.coverage.recompute", {})
            assert covered.status_code == 202, covered.text
            assert covered.json()["payload"]["weighted_percent"] is None

            # 3. Add the region the candidate will edit.
            applied = await send(
                "frontend.pxg.apply",
                {
                    "nodes": [
                        {
                            "pxg_key": "screens/checkout#hero",
                            "node_kind": "region",
                            "title": "Hero",
                            "parent_key": "screens/checkout",
                            "attributes": {"spacing": "space2"},
                        }
                    ]
                },
            )
            assert applied.status_code == 202, applied.text
            accepted_revision = applied.json()["payload"]["pxg_revision"]

            # 4. Create an isolated candidate and bring it to READY.
            created = await send(
                "frontend.candidate.create",
                {
                    "title": "Direction A",
                    "origin": "DIRECT_EDIT",
                    "scope_keys": ["screens/checkout"],
                },
            )
            assert created.status_code == 202, created.text
            candidate_id = created.json()["payload"]["candidate_id"]
            assert created.json()["payload"]["base_pxg_revision"] == (accepted_revision)

            for target in (
                "GENERATING",
                "GENERATED",
                "MATERIALIZING",
                "RENDERING",
                "READY",
            ):
                moved = await send(
                    "frontend.candidate.transition",
                    {"candidate_id": candidate_id, "target": target},
                )
                assert moved.status_code == 202, moved.text

            # An illegal jump is refused by the lifecycle table, not the UI.
            illegal = await send(
                "frontend.candidate.transition",
                {"candidate_id": candidate_id, "target": "PROMOTED"},
            )
            assert illegal.status_code == 403
            assert illegal.json()["error_code"] == "POLICY_DENIED"

            # 5. Edit through the one write path. A freehand literal is
            #    refused alongside a valid token in the same batch, and both
            #    answers come back.
            mutated = await send(
                "frontend.mutation.apply",
                {
                    "candidate_id": candidate_id,
                    "mutations": [
                        {
                            "operation": "SET_PROPERTY",
                            "target_key": "screens/checkout#hero",
                            "origin": "INSPECTOR",
                            "payload": {"property": "spacing", "value": "space6"},
                        },
                        {
                            "operation": "SET_PROPERTY",
                            "target_key": "screens/checkout#hero",
                            "origin": "CHAT",
                            "payload": {"property": "color", "value": "#ff0000"},
                        },
                    ],
                },
            )
            assert mutated.status_code == 202, mutated.text
            payload = mutated.json()["payload"]
            assert len(payload["applied"]) == 1
            assert payload["refused"][0]["refusal_code"] == "OFF_TOKEN_REFUSED"
            assert payload["fully_applied"] is False
            assert payload["candidate_state"] == "DIRTY"

            # 6. The accepted graph is untouched by that edit.
            accepted = await PxgService(engine).load(**scope)
            hero = accepted.node_by_key("screens/checkout#hero")
            assert hero is not None
            assert hero.attributes["spacing"] == "space2"

            # 7. A lock stops every affordance equally.
            locked = await send(
                "frontend.lock.create",
                {
                    "lock_kind": "STYLE",
                    "scope_key": "screens/checkout",
                    "reason": "brand review",
                },
            )
            assert locked.status_code == 202, locked.text
            lock_id = locked.json()["payload"]["lock_id"]

            blocked = await send(
                "frontend.mutation.apply",
                {
                    "candidate_id": candidate_id,
                    "mutations": [
                        {
                            "operation": "SET_PROPERTY",
                            "target_key": "screens/checkout#hero",
                            "origin": "DESIGN_PROVIDER",
                            "payload": {"property": "spacing", "value": "space8"},
                        }
                    ],
                },
            )
            assert blocked.status_code == 202, blocked.text
            assert blocked.json()["payload"]["refused"][0]["refusal_code"] == (
                "LOCK_DENIED"
            )

            released = await send("frontend.lock.release", {"lock_id": lock_id})
            assert released.status_code == 202, released.text
            assert released.json()["payload"]["status"] == "RELEASED"

            # 8. Promotion is denied without verification evidence, and the
            #    denial names every blocking gate.
            for target in ("VERIFYING", "VERIFIED", "PROMOTABLE"):
                moved = await send(
                    "frontend.candidate.transition",
                    {"candidate_id": candidate_id, "target": target},
                )
                assert moved.status_code == 202, moved.text

            denied = await send(
                "frontend.candidate.promote", {"candidate_id": candidate_id}
            )
            assert denied.status_code == 403, denied.text
            gates = {item["gate"] for item in denied.json()["details"]["blockers"]}
            assert "visual_verification" in gates

            # The accepted graph still has not moved: a denied promotion
            # writes nothing.
            accepted = await PxgService(engine).load(**scope)
            assert accepted.revision == accepted_revision
            hero = accepted.node_by_key("screens/checkout#hero")
            assert hero is not None and hero.attributes["spacing"] == "space2"
    finally:
        if workspace is not None:
            with suppress(Exception):
                await WorkspaceService(engine, root=repo_root()).cleanup(
                    workspace=workspace
                )
        await engine.dispose()


@pytest.mark.asyncio
async def test_chat_and_design_through_the_command_boundary(tmp_path) -> None:
    """M9/M10 through the real Gateway.

    The valuable assertion is the refusal: with no certified design
    provider, `/design` must come back as a typed unavailable state and
    never as a generic code-generation substitute.
    """
    engine = new_engine()
    app.state.engine = engine
    workspace = None
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-FS69-CHAT"
        )
        workspace = worker.workspace
        tenant = worker.tenant
        await _grant(
            engine,
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            principal_id=tenant.principal_id,
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            opened = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(tenant.principal_id),
                    "client_type": "human",
                    "scopes": ["mission.read", "mission.control"],
                    "subscriptions": ["mission"],
                },
            )
            assert opened.status_code == 201, opened.text
            session_id = opened.json()["session_id"]
            counter = {"n": 0}

            async def send(command_type: str, parameters: dict) -> httpx.Response:
                counter["n"] += 1
                return await client.post(
                    "/v1/commands",
                    json={
                        "command_id": str(uuid7()),
                        "idempotency_key": f"chat-{counter['n']}",
                        "principal_id": str(tenant.principal_id),
                        "client_session_id": str(session_id),
                        "target_type": "mission",
                        "target_id": str(worker.mission.mission_id),
                        "command_type": command_type,
                        "parameters": parameters,
                        "requested_at": datetime.now(UTC).isoformat(),
                        "protocol_version": "1",
                    },
                )

            await send(
                "frontend.pxg.apply",
                {
                    "nodes": [
                        {
                            "pxg_key": "screens/checkout",
                            "node_kind": "screen",
                            "title": "Checkout",
                        }
                    ]
                },
            )

            # The /design control's own state, read from the registry.
            status = await send("frontend.design.provider_status", {})
            assert status.status_code == 202, status.text
            providers = status.json()["payload"]["providers"]
            claude = next(
                item for item in providers if item["provider_id"] == "claude-design"
            )
            assert claude["usable"] is False
            assert claude["state"] == "NOT_CERTIFIED"
            assert "section 23" in claude["detail"]

            # A direct /design request is refused with a typed code.
            refused = await send(
                "frontend.design.request",
                {
                    "scope_keys": ["screens/checkout"],
                    "instruction": "three hero alternatives",
                },
            )
            assert refused.status_code == 403, refused.text
            assert refused.json()["error_code"] == "CAPABILITY_UNAVAILABLE"

            # The same ask through chat records a turn carrying the same
            # refusal, rather than failing silently or inventing an answer.
            conversation = await send("frontend.chat.open", {})
            assert conversation.status_code == 202, conversation.text
            conversation_id = conversation.json()["payload"]["conversation_id"]

            await send(
                "frontend.chat.set_context",
                {
                    "conversation_id": conversation_id,
                    "selected_node_keys": ["screens/checkout"],
                },
            )
            turn = await send(
                "frontend.chat.send",
                {
                    "conversation_id": conversation_id,
                    "text": "/design three hero alternatives",
                },
            )
            assert turn.status_code == 202, turn.text
            payload = turn.json()["payload"]
            assert payload["intent"] == "DESIGN_DIVERGENT"
            assert payload["outcome"] == "REFUSED"
            assert payload["refusal_code"] == "CAPABILITY_UNAVAILABLE"
            assert payload["produced_refs"] == []

            # An edit with no active candidate is refused for the right
            # reason: the accepted design is never edited in place.
            edit = await send(
                "frontend.chat.send",
                {
                    "conversation_id": conversation_id,
                    "text": "set the spacing to space6",
                },
            )
            assert edit.status_code == 202, edit.text
            assert edit.json()["payload"]["refusal_code"] == "NO_ACTIVE_CANDIDATE"
    finally:
        if workspace is not None:
            with suppress(Exception):
                await WorkspaceService(engine, root=repo_root()).cleanup(
                    workspace=workspace
                )
        await engine.dispose()
