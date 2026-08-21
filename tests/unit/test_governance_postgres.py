"""PostgreSQL-backed Chapter 13 approvals (DDE-026)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from engine.contracts.graph_amendment import GraphAmendment
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.governance.hashing import approval_scope_hash
from engine.governance.service import ApprovalService
from engine.missions.service import MissionService
from engine.planning.planner import PLANNER_POLICY_VERSION
from engine.recovery.workflow import MissionWorkflowService
from tests.support.db import new_engine, seed_tenant
from tests.unit.test_planning_postgres import REQUIREMENT_SLUG, _active_graph_fixture


class _ExpiredClock:
    def now(self) -> datetime:
        return datetime.now(UTC) + timedelta(hours=25)


@pytest.mark.asyncio
async def test_approval_cannot_be_reused_for_a_different_scope() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        mission = await MissionService(engine, EventService(engine)).create_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug=f"MISSION-APPR-{uuid7().hex[:12]}",
            title="Approvals",
            intent="Bind scope_hash",
            success_definition="Reuse is denied",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=2,
        )
        started = await MissionService(engine, EventService(engine)).transition_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            target_status="ACTIVE",
            lock_version=mission.lock_version,
        )
        service = ApprovalService(engine)
        bound = approval_scope_hash(
            approval_type="architecture_change",
            mission_id=started.mission_id,
            payload={"plan": "a"},
        )
        other = approval_scope_hash(
            approval_type="architecture_change",
            mission_id=started.mission_id,
            payload={"plan": "b"},
        )
        requested = await service.request(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=started.mission_id,
            approval_type="architecture_change",
            scope_hash=bound,
            requested_by=fixture.principal_id,
            idempotency_key="approval-bind-1",
        )
        with pytest.raises(DdeError) as captured:
            await service.decide(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                approval_id=requested.approval_id,
                decision="APPROVED",
                decided_by=fixture.principal_id,
                rationale="wrong plan",
                scope_hash=other,
            )
        assert captured.value.error_code == "POLICY_DENIED"
        approved = await service.decide(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            approval_id=requested.approval_id,
            decision="APPROVED",
            decided_by=fixture.principal_id,
            rationale="same plan",
            scope_hash=bound,
            human_minutes=12.5,
        )
        assert approved.status == "APPROVED"
        budget = await service.attention_budget(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=started.mission_id,
        )
        assert budget["human_minutes"] == 12.5
        assert budget["approvals_per_mission"] == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_standing_cannot_preauthorise_irreversible_or_production() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = ApprovalService(engine)
        with pytest.raises(DdeError) as captured:
            await service.grant_standing(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                approval_types=["irreversible_effect"],
                blast_radius_ceiling="module",
                risk_ceiling="medium",
                cost_ceiling=10.0,
                task_count_ceiling=4,
                path_scope=["engine"],
                forbidden_operations=[],
                valid_from_hours=0,
                valid_until_hours=8,
                granted_by=fixture.principal_id,
                rationale="overnight",
                idempotency_key="standing-irreversible-1",
            )
        assert captured.value.error_code == "POLICY_DENIED"
        with pytest.raises(DdeError):
            await service.grant_standing(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                approval_types=["oracle_approval"],
                blast_radius_ceiling="module",
                risk_ceiling="critical",
                cost_ceiling=10.0,
                task_count_ceiling=4,
                path_scope=["engine"],
                forbidden_operations=[],
                valid_from_hours=0,
                valid_until_hours=8,
                granted_by=fixture.principal_id,
                rationale="critical overnight",
                idempotency_key="standing-critical-1",
            )
        standing = await service.grant_standing(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            approval_types=["oracle_approval"],
            blast_radius_ceiling="module",
            risk_ceiling="medium",
            cost_ceiling=10.0,
            task_count_ceiling=4,
            path_scope=["engine"],
            forbidden_operations=[],
            valid_from_hours=0,
            valid_until_hours=8,
            granted_by=fixture.principal_id,
            rationale="overnight oracle",
            idempotency_key="standing-ok-1",
        )
        mission = await MissionService(engine, EventService(engine)).create_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug=f"MISSION-STAND-{uuid7().hex[:12]}",
            title="Standing",
            intent="Pre-authorise oracle",
            success_definition="Standing mints an approval",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=2,
        )
        digest = approval_scope_hash(
            approval_type="oracle_approval",
            mission_id=mission.mission_id,
            payload={"oracle": "v1"},
        )
        minted = await service.authorize_standing(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            standing_id=standing.standing_id,
            approval_type="oracle_approval",
            scope_hash=digest,
            requested_by=fixture.principal_id,
            mission_id=mission.mission_id,
            mission_scope=mission.scope,
            requested_paths=["engine/verification"],
            risk_class="low",
            blast_radius="local",
            idempotency_key="standing-mint-1",
        )
        assert minted.status == "APPROVED"
        assert minted.standing_id == standing.standing_id
        revoked = await service.revoke_standing(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            standing_id=standing.standing_id,
        )
        assert revoked.status == "REVOKED"
        with pytest.raises(DdeError):
            await service.authorize_standing(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                standing_id=standing.standing_id,
                approval_type="oracle_approval",
                scope_hash=digest,
                requested_by=fixture.principal_id,
                mission_id=mission.mission_id,
                mission_scope=mission.scope,
                requested_paths=["engine/verification"],
                risk_class="low",
                blast_radius="local",
                idempotency_key="standing-mint-2",
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_request_approval_blocks_only_the_named_task_and_enters_partial() -> None:
    engine = new_engine()
    try:
        (
            fixture,
            service,
            _task_graphs,
            mission,
            active,
            planned,
        ) = await _active_graph_fixture(engine, slug="MISSION-APPR-PARTIAL")
        started = await service.transition_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            target_status="ACTIVE",
            lock_version=mission.lock_version,
        )
        blocked = planned.tasks[1]
        workflow = MissionWorkflowService(engine, missions=service)
        approval = await workflow.request_approval(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=started.mission_id,
            approval_type="architecture_change",
            requested_by=fixture.principal_id,
            idempotency_key="workflow-approval-1",
            reason="architecture question",
            task_id=blocked.task_id,
        )
        assert approval.status == "REQUESTED"
        refreshed_task = await service.get_task(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            task_id=blocked.task_id,
        )
        refreshed_mission = await service.get_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=started.mission_id,
        )
        independent = await service.get_task(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            task_id=planned.tasks[0].task_id,
        )
        assert refreshed_task.status == "BLOCKED_ON_DECISION"
        assert refreshed_mission.status == "PARTIAL"
        assert independent.status != "BLOCKED_ON_DECISION"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_expired_approval_parks_the_mission() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        missions = MissionService(engine, EventService(engine))
        mission = await missions.create_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug=f"MISSION-PARK-{uuid7().hex[:12]}",
            title="Park",
            intent="Expiry parks",
            success_definition="PAUSED is not FAILED",
            scope=["engine"],
            requirement_refs=[],
            autonomy_ceiling=2,
        )
        started = await missions.transition_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            target_status="ACTIVE",
            lock_version=mission.lock_version,
        )
        live = ApprovalService(engine)
        digest = approval_scope_hash(
            approval_type="architecture_change",
            mission_id=started.mission_id,
            payload={"park": True},
        )
        requested = await live.request(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=started.mission_id,
            approval_type="architecture_change",
            scope_hash=digest,
            requested_by=fixture.principal_id,
            idempotency_key="park-1",
        )
        expired_service = ApprovalService(engine, clock=_ExpiredClock())
        workflow = MissionWorkflowService(
            engine, missions=missions, approvals=expired_service
        )
        parked = await workflow.expire_and_park(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission=started,
            approval_id=requested.approval_id,
        )
        assert parked.status == "PAUSED"
        items = await expired_service.list_attention(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=started.mission_id,
        )
        kinds = {item.kind for item in items}
        assert "expired_approval" in kinds
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_approved_widen_scope_amendment_is_accepted() -> None:
    engine = new_engine()
    try:
        (
            fixture,
            service,
            _task_graphs,
            mission,
            active,
            _planned,
        ) = await _active_graph_fixture(engine, slug="MISSION-APPR-WIDEN")
        digest = approval_scope_hash(
            approval_type="scope_widening",
            mission_id=mission.mission_id,
            payload={"paths": ["secret/other-project"]},
        )
        approvals = ApprovalService(engine)
        requested = await approvals.request(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            approval_type="scope_widening",
            scope_hash=digest,
            requested_by=fixture.principal_id,
            idempotency_key="widen-1",
        )
        await approvals.decide(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            approval_id=requested.approval_id,
            decision="APPROVED",
            decided_by=fixture.principal_id,
            rationale="accepted widening",
            scope_hash=digest,
        )
        amendment = GraphAmendment(
            amendment_id=uuid7(),
            graph_id=active.graph_id,
            proposed_by="principal",
            amendment_type="widen_scope",
            justification="approved extra path",
            evidence_refs=[],
            affected_task_ids=[],
            requested_write_scope=["secret/other-project"],
        )
        amended = await service.amend_task_graph(
            mission=mission,
            amendment=amendment,
            new_graph_id=uuid7(),
            new_tasks=[],
            new_edges=[],
            planner_policy_version=PLANNER_POLICY_VERSION,
            created_by_principal=fixture.principal_id,
            approved_requirement_slugs={REQUIREMENT_SLUG},
            approval_scope_hash=digest,
        )
        assert amended.status == "ACTIVE"
        assert amended.supersedes_id == active.graph_id
    finally:
        await engine.dispose()
