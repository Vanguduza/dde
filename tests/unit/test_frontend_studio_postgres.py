"""PostgreSQL proofs for DDE-067 Frontend Studio Gateway commands."""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from engine.context.repo import repo_root
from engine.core.ids import uuid7
from engine.studio.tokens_pin import tokens_file_hash
from engine.workspaces.service import WorkspaceService
from interfaces.api import app
from tests.support.db import new_engine, seed_tenant
from tests.support.worker_fixtures import build_worker_fixture

STARTER = b"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8" /></head>
<body></body></html>
"""

FLOWS = b"""{
  "version": 1,
  "flows": [
    {
      "id": "checkout",
      "entry": "cart.ready.html",
      "steps": [
        {"from": "cart.ready.html", "on": "[data-dde-el=pay]", "to": "pay.ready.html"}
      ]
    }
  ]
}
"""


def _art() -> dict[str, object]:
    return {
        "record_id": "ad-1",
        "product_id": "p1",
        "version": "1",
        "design_read": "Settings form for operators; English; token foundation.",
        "dials": {
            "DESIGN_VARIANCE": 3,
            "MOTION_INTENSITY": 2,
            "VISUAL_DENSITY": 5,
        },
        "type_pairing": {
            "pairing_id": "source-serif-sans",
            "display": "Source Serif 4",
            "body": "Source Sans 3",
        },
        "palette_roles": {
            "canvas": "surfaceBase",
            "surface": "surfaceCard",
            "ink": "textPrimary",
            "accent": "accentPrimary",
            "semantic_ok": "statusOk",
            "semantic_warn": "statusWarn",
            "semantic_err": "statusErr",
        },
        "theme_atmosphere": "Restrained.",
        "typography_hierarchy": "Serif display, sans body.",
        "component_stylings": [{"component": "field", "states": ["idle", "error"]}],
        "layout_idiom": "settings form",
        "layout_principles": "One pattern.",
        "depth_elevation": "overlay token only",
        "dos_donts": {"dos": ["tokens"], "donts": ["hex"]},
        "responsive_behavior": "stack at 960px",
        "agent_prompt_guide": "Stay on tokens.",
        "motion_identity": "restrained",
    }


def _compile_params() -> dict[str, object]:
    return {
        "prd_id": "prd-ledgerline",
        "prd_version": "1",
        "playbook_version": "1.2",
        "tokens_version": 1,
        "tokens_hash": tokens_file_hash(),
        "art_direction": _art(),
        "requirements": [
            {
                "requirement_id": "req-1",
                "slug": "REQ-LL-001",
                "statement": "Clerks can post a balanced journal.",
                "status": "approved",
            }
        ],
        "features": [
            {
                "feature_id": "feat-journals",
                "title": "Journal worklist",
                "purpose": "Post and review journals.",
                "layout_pattern": "columnar-worklist",
                "states": ["idle", "loading", "empty", "error", "disabled"],
            }
        ],
    }


async def _seed_grant(engine, *, tenant_id, principal_id, project_id) -> None:
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


def _command_body(
    *,
    key: str,
    session_id,
    principal_id,
    target_id,
    command_type,
    parameters,
) -> dict:
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


@pytest.mark.asyncio
async def test_compile_prompt_round_trip_and_replay() -> None:
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
            slug=f"MISSION-FS-{uuid7().hex[:12]}",
            title="Frontend compile",
            intent="Compile a generation prompt",
            success_definition="Gateway compile_prompt accepted",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=2,
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            opened = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(fixture.principal_id),
                    "client_type": "human",
                    "scopes": ["mission.read", "mission.control", "approval.request"],
                    "subscriptions": ["mission"],
                },
            )
            assert opened.status_code == 201, opened.text
            session = opened.json()
            body = _command_body(
                key="fs-compile-1",
                session_id=session["session_id"],
                principal_id=fixture.principal_id,
                target_id=mission.mission_id,
                command_type="frontend.intake.compile_prompt",
                parameters=_compile_params(),
            )
            accepted = await client.post("/v1/commands", json=body)
            assert accepted.status_code == 202, accepted.text
            payload = accepted.json()["payload"]
            assert payload["content_hash"]
            assert payload["prd_id"] == "prd-ledgerline"
            replayed = await client.post("/v1/commands", json=body)
            assert replayed.status_code == 202
            assert replayed.json()["payload"]["content_hash"] == payload["content_hash"]

            missing = dict(_compile_params())
            missing["art_direction"] = None
            refused = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs-compile-missing-art",
                    session_id=session["session_id"],
                    principal_id=fixture.principal_id,
                    target_id=mission.mission_id,
                    command_type="frontend.intake.compile_prompt",
                    parameters=missing,
                ),
            )
            assert refused.status_code == 409
            error = refused.json()
            assert error["error_code"] == "CONTEXT_INCOMPLETE"
            assert error["details"]["missing_artifact"] == "art_direction"

            # DDE-068 closed GUI-spec open item D2: pixel sign-off is now a
            # real admitted approval type, so the escalation the bounded
            # visual-revision loop lands on creates a real Approval row
            # instead of refusing.
            signoff = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs-signoff-1",
                    session_id=session["session_id"],
                    principal_id=fixture.principal_id,
                    target_id=mission.mission_id,
                    command_type="frontend.prototype.request_pixel_signoff",
                    parameters={
                        "screen_ref": "screens/overview",
                        "rubric_version": "1",
                        "failing_dimensions": ["accessibility"],
                    },
                ),
            )
            assert signoff.status_code == 202, signoff.text
            payload = signoff.json()["payload"]
            assert payload["approval_type"] == "prototype_pixel_signoff"
            assert payload["status"] == "REQUESTED"
            assert payload["screen_ref"] == "screens/overview"
            assert payload["failing_dimensions"] == ["accessibility"]
            assert payload["scope_hash"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_canvas_insert_token_refusal_and_donor_reuse(
    tmp_path,
) -> None:
    engine = new_engine()
    app.state.engine = engine
    workspace = None
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-FS-CANVAS-1"
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
        spaces.write(worker.workspace, "prototypes/flows.json", FLOWS)

        from engine.donor.service import DonorLabService

        pin = await DonorLabService(engine).submit_uri(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
            source_uri="file:///fixtures/donor/mit.md",
            idempotency_key="fs-donor-pin-1",
            content=b"# SPDX-License-Identifier: MIT\n\nReuse me.\n",
            media_kind="licence_text",
            mission_id=worker.mission.mission_id,
        )
        assert pin.artifact.source_class == "OPEN_REUSE"

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            opened = await client.post(
                "/v1/sessions",
                json={
                    "principal_id": str(worker.tenant.principal_id),
                    "client_type": "human",
                    "scopes": ["mission.read", "mission.control", "approval.request"],
                    "subscriptions": ["mission"],
                },
            )
            assert opened.status_code == 201, opened.text
            session = opened.json()
            sid = session["session_id"]
            pid = worker.tenant.principal_id
            mid = worker.mission.mission_id
            ws = str(worker.workspace.workspace_id)

            base = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs-insert-base",
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

            hex_edit = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs-hex-edit",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.canvas.update_element",
                    parameters={
                        "workspace_id": ws,
                        "screen_file": "cart.ready.html",
                        "element_id": element_id,
                        "property": "color",
                        "value": "#1177bb",
                    },
                ),
            )
            assert hex_edit.status_code == 403
            token_edit = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs-token-edit",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.canvas.update_element",
                    parameters={
                        "workspace_id": ws,
                        "screen_file": "cart.ready.html",
                        "element_id": element_id,
                        "property": "color",
                        "value": "--accent-primary",
                    },
                ),
            )
            assert token_edit.status_code == 202, token_edit.text

            blocked = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs-insert-donor-blocked",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.canvas.insert_component",
                    parameters={
                        "workspace_id": ws,
                        "screen_file": "cart.ready.html",
                        "component_ref": "button",
                        "anchor_parent": "root",
                        "position_index": 1,
                        "label": "Donor button",
                        "donor_id": str(pin.artifact.donor_artifact_id),
                    },
                ),
            )
            assert blocked.status_code == 403
            assert blocked.json()["details"]["approval_type"] == "donor_reuse"

            adopt = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs-adopt-1",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.donors.request_adoption",
                    parameters={
                        "donor_artifact_id": str(pin.artifact.donor_artifact_id)
                    },
                ),
            )
            assert adopt.status_code == 202, adopt.text
            from engine.governance.service import ApprovalService

            await ApprovalService(engine).decide(
                tenant_id=worker.tenant.tenant_id,
                project_id=worker.tenant.project_id,
                approval_id=UUID(adopt.json()["payload"]["approval_id"]),
                decision="APPROVED",
                decided_by=pid,
                rationale="Adopt MIT donor for canvas insert",
                scope_hash=adopt.json()["payload"]["scope_hash"],
            )
            allowed = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs-insert-donor-ok",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.canvas.insert_component",
                    parameters={
                        "workspace_id": ws,
                        "screen_file": "cart.ready.html",
                        "component_ref": "button",
                        "anchor_parent": "root",
                        "position_index": 1,
                        "label": "Donor button",
                        "donor_id": str(pin.artifact.donor_artifact_id),
                    },
                ),
            )
            assert allowed.status_code == 202, allowed.text

            motion = await client.post(
                "/v1/commands",
                json=_command_body(
                    key="fs-motion-1",
                    session_id=sid,
                    principal_id=pid,
                    target_id=mid,
                    command_type="frontend.motion.set_animation",
                    parameters={
                        "workspace_id": ws,
                        "flow_id": "checkout",
                        "step_index": 0,
                        "animation": {
                            "durationToken": "motion-duration-base",
                            "easingToken": "motion-easing-state",
                            "reducedMotionVariant": True,
                        },
                    },
                ),
            )
            assert motion.status_code == 202, motion.text
    finally:
        if workspace is not None:
            with suppress(Exception):
                await WorkspaceService(engine, root=repo_root()).cleanup(
                    workspace=workspace
                )
        await engine.dispose()
