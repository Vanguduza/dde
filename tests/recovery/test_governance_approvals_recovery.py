"""Chapter 19.1 recovery: approvals persist across process-local engines."""

from __future__ import annotations

import pytest

from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.governance.hashing import approval_scope_hash
from engine.governance.service import ApprovalService
from engine.missions.service import MissionService
from tests.support.db import new_engine, seed_tenant


@pytest.mark.asyncio
async def test_approved_row_is_visible_to_a_new_engine() -> None:
    writer = new_engine()
    reader = new_engine()
    try:
        fixture = await seed_tenant(writer)
        mission = await MissionService(writer, EventService(writer)).create_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug=f"MISSION-APPR-RECOVERY-{uuid7().hex[:12]}",
            title="Recovery",
            intent="Approvals are not process-local",
            success_definition="A second engine reads APPROVED",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=2,
        )
        digest = approval_scope_hash(
            approval_type="architecture_change",
            mission_id=mission.mission_id,
            payload={"recovery": True},
        )
        writer_svc = ApprovalService(writer)
        requested = await writer_svc.request(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            approval_type="architecture_change",
            scope_hash=digest,
            requested_by=fixture.principal_id,
            idempotency_key="approval-recovery-1",
        )
        await writer_svc.decide(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            approval_id=requested.approval_id,
            decision="APPROVED",
            decided_by=fixture.principal_id,
            rationale="durable",
            scope_hash=digest,
        )
        found = await ApprovalService(reader).require_approved(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            scope_hash=digest,
            approval_type="architecture_change",
        )
        assert found.status == "APPROVED"
        assert found.approval_id == requested.approval_id
    finally:
        await writer.dispose()
        await reader.dispose()
