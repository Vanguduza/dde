"""DDE-069 — the `/design` path against real infrastructure and real Claude.

This is the certification run, and it is gated for two independent reasons.
It spends a real Claude Design invocation on the operator's own seat, and it
needs real PostgreSQL, real Redis and a real git worktree. Neither belongs
in an ordinary unit run, so `just check` never reaches this directory and
the module skips outright unless the operator opts in:

    DDE_LIVE_CLAUDE_DESIGN=1 \\
    DDE_CLAUDE_DESIGN_ENABLED=1 \\
    DDE_DATABASE_URL=... DDE_REDIS_URL=... \\
    pytest tests/live/test_claude_design_live_e2e.py

What it proves, in one uninterrupted chain through `/v1/commands`:

1. the Claude Design provider reports CERTIFIED from a discovered
   transport, not from a fixture;
2. `/design` typed into Universal DDE Chat routes to the DesignGateway and
   persists a DesignSession plus real DesignArtifacts, with provider,
   context-manifest and design-system-hash provenance;
3. Try live turns one artifact into an *isolated* candidate, leaving the
   accepted PXG untouched;
4. that candidate's preview reaches LIVE only after a real code-backed
   render and a browser content-hash handshake;
5. promotion still runs the DDE verification gate, and is refused when the
   evidence for it does not exist.

Point 5 is the one worth stating plainly: this test asserts that promotion
is *blocked*. A run in which a design artifact reached accepted state
without verification evidence would be a failure of the system, not a
success of the test.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from engine.context.repo import repo_root
from engine.core.ids import uuid7
from engine.studio.candidates.service import CandidateService
from engine.studio.design.gateway import DesignGateway
from engine.studio.mutations.executor import MutationExecutor
from engine.studio.pxg.service import PxgService
from engine.workspaces.service import WorkspaceService
from interfaces.api import app
from tests.support.db import new_engine
from tests.support.worker_fixtures import build_worker_fixture

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("DDE_LIVE_CLAUDE_DESIGN", "").strip().lower()
        not in {"1", "true", "yes", "on"},
        reason=(
            "live Claude Design certification is opt-in: it spends a real "
            "provider invocation. Set DDE_LIVE_CLAUDE_DESIGN=1."
        ),
    ),
]

#: When set, the run records what it observed as JSON. Evidence is a
#: by-product of the assertions, never a separately authored claim.
EVIDENCE_ENV = "DDE_LIVE_DESIGN_EVIDENCE"

SCREEN_KEY = "screens/checkout"
HERO_KEY = "screens/checkout#hero"
SOURCE_PATH = "prototypes/screens/checkout.html"

#: A real prototype page. `data-dde-el` is the stable anchor the preview
#: adapter maps a PXG node onto, so this is code the candidate edits, not a
#: screenshot standing in for one.
PROTOTYPE = (
    "<!DOCTYPE html>\n"
    '<html lang="en"><head><meta charset="UTF-8" /><title>Checkout</title></head>\n'
    "<body>\n"
    '  <div data-dde-el="hero-1" data-dde-kind="layout" '
    'style="padding: var(--space-2)">Hero</div>\n'
    "</body></html>\n"
)


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


def _commit_prototype(workspace_path: str) -> None:
    """Give the source workspace a real revision carrying real code.

    A workspace's `current_revision` is a git commit, and the candidate
    worktree is created *from that revision* -- so writing the file without
    committing it would produce a candidate whose source does not contain
    the screen. Test setup only: production code never commits here.
    """
    run = ["git", "-C", workspace_path]
    subprocess.run([*run, "add", SOURCE_PATH], check=True, capture_output=True)  # noqa: S603, S607
    subprocess.run(  # noqa: S603, S607
        [
            *run,
            "-c",
            "user.email=live-e2e@dde.invalid",
            "-c",
            "user.name=DDE live E2E",
            "commit",
            "-m",
            "DDE-069 live E2E prototype source",
        ],
        check=True,
        capture_output=True,
    )


@pytest.mark.asyncio
async def test_claude_design_reaches_live_and_still_faces_the_promotion_gate(
    tmp_path,
) -> None:
    engine = new_engine()
    app.state.engine = engine
    workspace = None
    evidence: dict[str, object] = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "transport": {
            "binary": os.environ.get("DDE_CLAUDE_DESIGN_BINARY", "claude"),
            "model": os.environ.get("DDE_CLAUDE_DESIGN_MODEL"),
        },
    }
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-FS69-LIVE-DESIGN"
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

        spaces = WorkspaceService(engine, root=repo_root())
        spaces.write(workspace, SOURCE_PATH, PROTOTYPE.encode("utf-8"))
        assert workspace.workspace_path is not None
        _commit_prototype(workspace.workspace_path)
        source_workspace = await spaces.capture_revision(workspace=workspace)
        assert source_workspace.current_revision is not None
        assert source_workspace.status == "READY", source_workspace.status

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", timeout=1200.0
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
                        "idempotency_key": f"live-design-{counter['n']}",
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

            # --- 1. a real project surface to design against ------------
            registered = await send(
                "frontend.screen.register",
                {
                    "task_id": str(worker.task.task_id),
                    "screen_ref": SCREEN_KEY,
                    "title": "Checkout",
                    "preview_url": "file:///tmp/checkout.html",
                    "route": "/checkout",
                },
            )
            assert registered.status_code == 202, registered.text

            published = await send(
                "frontend.contract.publish",
                {
                    "obligations": [
                        {
                            "dimension": "screen",
                            "pxg_key": SCREEN_KEY,
                            "statement": "Checkout exists",
                            "applicability": "REQUIRED",
                        },
                        {
                            "dimension": "accessibility",
                            "pxg_key": SCREEN_KEY,
                            "statement": "Checkout meets AA",
                            "applicability": "REQUIRED",
                            "verification_kinds": ["visual_critique"],
                        },
                    ]
                },
            )
            assert published.status_code == 202, published.text

            applied = await send(
                "frontend.pxg.apply",
                {
                    "nodes": [
                        {
                            "pxg_key": SCREEN_KEY,
                            "node_kind": "screen",
                            "title": "Checkout",
                            "attributes": {"route": "/checkout"},
                            "source_refs": [
                                {"path": SOURCE_PATH, "symbol": "Checkout"}
                            ],
                        },
                        {
                            "pxg_key": HERO_KEY,
                            "node_kind": "region",
                            "title": "Hero",
                            "parent_key": SCREEN_KEY,
                            "attributes": {
                                "spacing": "space2",
                                "element_id": "hero-1",
                            },
                            "source_refs": [{"path": SOURCE_PATH, "symbol": "Hero"}],
                        },
                    ]
                },
            )
            assert applied.status_code == 202, applied.text
            accepted_revision = applied.json()["payload"]["pxg_revision"]

            # --- 2. the provider is certified from discovery -----------
            status = await send("frontend.design.provider_status", {})
            assert status.status_code == 202, status.text
            claude = next(
                item
                for item in status.json()["payload"]["providers"]
                if item["provider_id"] == "claude-design"
            )
            evidence["provider_status"] = claude
            assert claude["state"] == "CERTIFIED", claude
            assert claude["usable"] is True
            # Discovered identity, not a constant: an unauthenticated or
            # unreachable host could not have produced this.
            assert claude["version"], claude

            # --- 3. `/design` through Universal DDE Chat ---------------
            conversation = await send(
                "frontend.chat.open",
                {"viewport": "desktop-1440", "screen_key": SCREEN_KEY},
            )
            assert conversation.status_code == 202, conversation.text
            conversation_id = conversation.json()["payload"]["conversation_id"]

            moded = await send(
                "frontend.chat.set_mode",
                {"conversation_id": conversation_id, "mode": "EXECUTE"},
            )
            assert moded.status_code == 202, moded.text

            contexted = await send(
                "frontend.chat.set_context",
                {
                    "conversation_id": conversation_id,
                    "selected_node_keys": [SCREEN_KEY],
                    "screen_key": SCREEN_KEY,
                    "viewport": "desktop-1440",
                },
            )
            assert contexted.status_code == 202, contexted.text

            designed = await send(
                "frontend.chat.send",
                {
                    "conversation_id": conversation_id,
                    "text": (
                        f"/design two alternative hero directions for {SCREEN_KEY}, "
                        "denser and calmer"
                    ),
                },
            )
            assert designed.status_code == 202, designed.text
            turn = designed.json()["payload"]
            evidence["design_turn"] = turn
            assert turn["intent"] == "DESIGN_DIVERGENT", turn
            assert turn["outcome"] == "ROUTED", (
                turn.get("refusal_code"),
                turn.get("refusal_detail"),
            )
            assert turn["produced_refs"], turn

            # The design session belongs to *this* conversation: the
            # toolbar control and the composer share one lineage rather
            # than each opening their own.
            design_session_id = await _design_session_of(engine, conversation_id)
            assert design_session_id is not None
            directions_read = await client.get(
                f"/v1/missions/{worker.mission.mission_id}/frontend/design/sessions/"
                f"{design_session_id}/artifacts",
                headers={
                    "X-Session-Id": str(session_id),
                    "X-Principal-Id": str(tenant.principal_id),
                },
            )
            assert directions_read.status_code == 200, directions_read.text
            persisted_directions = directions_read.json()["artifacts"]
            assert persisted_directions, (
                "the workbench design-artifact read returned no rows"
            )

            artifacts = await DesignGateway(engine).artifacts_for(
                **scope, session_id=design_session_id
            )
            assert artifacts, "the live provider returned no artifacts"
            assert {item["artifact_id"] for item in persisted_directions} == {
                str(item.artifact_id) for item in artifacts
            }
            usable = [item for item in artifacts if item.status == "GENERATED"]
            assert usable, [item.quarantine_reason for item in artifacts]
            for artifact in usable:
                assert artifact.provider_id == "claude-design"
                assert artifact.provenance["design_system_hash"]
                assert artifact.provenance["provider_version"]
                assert artifact.content["nodes"]
                assert artifact.content["provider_project_id"]
                # A direction is a proposal in the project's own token
                # vocabulary, never code and never a score.
                assert "score" not in artifact.content
            evidence["design_session_id"] = str(design_session_id)
            evidence["artifacts"] = [
                {
                    "artifact_id": str(item.artifact_id),
                    "direction_label": item.direction_label,
                    "status": item.status,
                    "content_hash": item.content_hash,
                    "provider_id": item.provider_id,
                    "provenance": item.provenance,
                    "provider_project_id": item.content.get("provider_project_id"),
                    "provider_project_url": item.content.get("provider_project_url"),
                    "preview_path": item.content.get("preview_path"),
                    "summary": item.content.get("summary"),
                    "nodes": item.content.get("nodes"),
                }
                for item in artifacts
            ]

            # --- 4. Try live: artifact -> isolated candidate -----------
            tried = await send(
                "frontend.design.try_live",
                {"artifact_id": str(usable[0].artifact_id)},
            )
            assert tried.status_code == 202, tried.text
            candidate_id = tried.json()["payload"]["candidate_id"]
            evidence["try_live"] = tried.json()["payload"]

            # Try live now materializes the selected direction itself: the
            # candidate is GENERATED with an exact governed mutation log,
            # while accepted PXG remains untouched.
            accepted = await PxgService(engine).load(**scope)
            assert accepted.revision == accepted_revision
            hero = accepted.node_by_key(HERO_KEY)
            assert hero is not None and hero.attributes["spacing"] == "space2"

            candidate = await CandidateService(engine).get(
                **scope, candidate_id=UUID(candidate_id)
            )
            assert candidate.state == "GENERATED"
            assert candidate.origin == "DESIGN_ARTIFACT"
            history = await MutationExecutor(engine).history(
                **scope, candidate_id=UUID(candidate_id)
            )
            assert history and all(item.status == "APPLIED" for item in history)
            assert all(item.origin == "DESIGN_PROVIDER" for item in history)
            proposed = usable[0].content["nodes"]
            expected_pairs = {
                (str(node["pxg_key"]), str(prop), str(value))
                for node in proposed
                for prop, value in node["tokens"].items()
            }
            observed_pairs = {
                (
                    item.target_key,
                    str(item.payload.get("property")),
                    str(item.payload.get("value")),
                )
                for item in history
            }
            assert observed_pairs == expected_pairs
            evidence["try_live"]["materialized_mutations"] = [
                {
                    "target_key": item.target_key,
                    "property": item.payload.get("property"),
                    "value": item.payload.get("value"),
                    "status": item.status,
                }
                for item in history
            ]

            # --- 5. a code-backed preview, then the LIVE handshake -----
            started = await send(
                "frontend.preview.start",
                {
                    "candidate_id": candidate_id,
                    "screen_key": SCREEN_KEY,
                    "viewport": "desktop-1440",
                    "source_workspace_id": str(source_workspace.workspace_id),
                },
            )
            assert started.status_code == 202, started.text
            preview = started.json()["payload"]
            assert preview["state"] == "LOADING", preview
            assert preview["source_path"] == SOURCE_PATH
            content_hash = preview["content_hash"]
            assert content_hash

            # The hash is the real candidate file's, not an assertion.
            candidate_workspace = await spaces.get_workspace(
                **scope, workspace_id=UUID(preview["workspace_id"])
            )
            on_disk = spaces.read(candidate_workspace, SOURCE_PATH)
            assert hashlib.sha256(on_disk).hexdigest() == content_hash
            rendered_html = on_disk.decode("utf-8")
            for target_key, prop, value in expected_pairs:
                assert target_key == HERO_KEY
                attr = f'data-dde-{prop.replace("_", "-")}="{value}"'
                assert attr in rendered_html, (attr, rendered_html)
            assert on_disk != PROTOTYPE.encode("utf-8"), (
                "Try live rendered the unchanged base prototype rather than "
                "the selected Claude Design direction"
            )

            # A wrong hash is refused rather than rounded up to LIVE.
            mismatched = await send(
                "frontend.preview.set_state",
                {
                    "preview_session_id": preview["preview_session_id"],
                    "state": "LIVE",
                    "content_hash": "0" * 64,
                },
            )
            assert mismatched.status_code == 202, mismatched.text
            assert mismatched.json()["payload"]["state"] == "STALE"

            restarted = await send(
                "frontend.preview.start",
                {
                    "candidate_id": candidate_id,
                    "screen_key": SCREEN_KEY,
                    "viewport": "desktop-1440",
                },
            )
            assert restarted.status_code == 202, restarted.text
            fresh = restarted.json()["payload"]
            assert fresh["state"] == "LOADING", fresh

            live = await send(
                "frontend.preview.set_state",
                {
                    "preview_session_id": fresh["preview_session_id"],
                    "state": "LIVE",
                    "content_hash": fresh["content_hash"],
                },
            )
            assert live.status_code == 202, live.text
            assert live.json()["payload"]["state"] == "LIVE", live.text
            evidence["preview"] = {
                "rejected_hash_state": mismatched.json()["payload"]["state"],
                "live": live.json()["payload"],
            }

            # --- 6. verification still gates promotion -----------------
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
            blockers = {item["gate"] for item in denied.json()["details"]["blockers"]}
            evidence["promotion_denied"] = denied.json()
            assert "visual_verification" in blockers, blockers

            # Nothing a design provider produced reached accepted state.
            final = await PxgService(engine).load(**scope)
            assert final.revision == accepted_revision
            final_hero = final.node_by_key(HERO_KEY)
            assert final_hero is not None
            assert final_hero.attributes["spacing"] == "space2"
            evidence["accepted_pxg_revision_unchanged"] = accepted_revision
    finally:
        destination = os.environ.get(EVIDENCE_ENV, "").strip()
        if destination:
            Path(destination).write_text(
                json.dumps(evidence, indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )
        if workspace is not None:
            with suppress(Exception):
                await WorkspaceService(engine, root=repo_root()).cleanup(
                    workspace=workspace
                )
        await engine.dispose()


async def _design_session_of(engine, conversation_id: str):
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT design_session_id FROM frontend_conversations "
                    "WHERE conversation_id = :c"
                ),
                {"c": conversation_id},
            )
        ).first()
    return None if row is None else row[0]
