"""Chapter 13.1 durable-approvals hardening: batch decisions, the
decision audit trail, and the human budget-increase workflow
(Ch.7.1/12.3 pause-for-human path). PostgreSQL-backed (Chapter 19.1):
every test here exercises the production writers under real RLS-scoped
transactions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select

from engine.audit.service import AuditService
from engine.audit.tables import audit_events
from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.execution.hashing import plan_hash
from engine.governance.hashing import approval_scope_hash
from engine.governance.service import ApprovalService
from engine.missions.service import MissionService
from engine.workers.budget import ATTEMPT_MAX_TOKENS_KEY, AttemptBudget
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine, seed_tenant
from tests.unit.test_budget_dispatch_exhaustion import build_capped_plan_fixture


class _BackdatedClock:
    """A clock 25 hours behind reality: approvals created through it
    carry an `expires_at` (created + 24h TTL) that is already one hour in
    the real past."""

    def now(self) -> datetime:
        return datetime.now(UTC) - timedelta(hours=25)


async def _mission(engine, fixture, *, slug: str) -> tuple[MissionService, object]:
    from engine.events.service import EventService

    missions = MissionService(engine, EventService(engine))
    mission = await missions.create_mission(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        slug=slug,
        title="Batch",
        intent="Batch decide",
        success_definition="All or nothing",
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
    return missions, started


def _slug(prefix: str) -> str:
    return f"MISSION-{prefix}-{uuid7().hex[:8]}"


async def _pending_approval(
    service: ApprovalService,
    fixture,
    mission_id: UUID,
    *,
    key: str,
    tag: str,
) -> object:
    return await service.request(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        mission_id=mission_id,
        approval_type="architecture_change",
        scope_hash=approval_scope_hash(
            approval_type="architecture_change",
            mission_id=mission_id,
            payload={"tag": tag},
        ),
        requested_by=fixture.principal_id,
        idempotency_key=key,
    )


async def _audit_rows_for(engine, fixture, event_type: str) -> list[dict[str, object]]:
    async with open_uow(engine, fixture) as uow:
        result = await uow.connection.execute(
            select(audit_events)
            .where(
                audit_events.c.tenant_id == fixture.tenant_id,
                audit_events.c.event_type == event_type,
            )
            .order_by(audit_events.c.sequence.asc())
        )
        rows = [dict(row) for row in result.mappings().all()]
        await uow.commit()
    return rows


def open_uow(engine, fixture):
    from engine.truth.db import open_unit_of_work

    return open_unit_of_work(
        engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
    )


# ---------------------------------------------------------------------------
# Durability of decisions: audit trail + cross-engine reads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decision_appends_audit_event_in_the_same_transaction() -> None:
    """Chapter 14.5 invariant 9: an approval decision produces an
    `audit_event` carrying who decided which bound scope; it lands in the
    hash-chained ledger durably, not just as a column on the row."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        _missions, mission = await _mission(engine, fixture, slug=_slug("AUD"))
        service = ApprovalService(engine)
        digest = approval_scope_hash(
            approval_type="architecture_change",
            mission_id=mission.mission_id,
            payload={"audit": True},
        )
        requested = await service.request(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            approval_type="architecture_change",
            scope_hash=digest,
            requested_by=fixture.principal_id,
            idempotency_key="audit-req-1",
        )
        decided = await service.decide(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            approval_id=requested.approval_id,
            decision="APPROVED",
            decided_by=fixture.principal_id,
            rationale="durable trail",
            scope_hash=digest,
        )
        assert decided.status == "APPROVED"

        rows = await _audit_rows_for(engine, fixture, "approval.decided")
        assert len(rows) == 1
        payload = rows[0]["payload"]
        assert payload["approval_id"] == str(requested.approval_id)
        assert payload["decision"] == "APPROVED"
        assert payload["decided_by"] == str(fixture.principal_id)
        assert payload["scope_hash"] == digest

        # The chain itself verifies after the decision.
        await AuditService(engine).verify_chain(tenant_id=fixture.tenant_id)

        # And the decision is readable through the ordinary gate.
        found = await service.require_approved(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            scope_hash=digest,
            approval_type="architecture_change",
        )
        assert found.approval_id == requested.approval_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_denied_and_batch_decisions_are_also_audited() -> None:
    """Denials are security-relevant too (Chapter 14.5 invariant 9), and a
    batch decision leaves one auditable command identity behind."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        _missions, mission = await _mission(engine, fixture, slug=_slug("AUD2"))
        service = ApprovalService(engine)
        first = await _pending_approval(
            service, fixture, mission.mission_id, key="audit-rej-1", tag="rej"
        )
        second = await _pending_approval(
            service, fixture, mission.mission_id, key="audit-batch-1", tag="batch"
        )
        digest_first = first.scope_hash
        digest_second = second.scope_hash
        await service.decide(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            approval_id=first.approval_id,
            decision="REJECTED",
            decided_by=fixture.principal_id,
            rationale="no",
            scope_hash=digest_first,
        )
        await service.batch_decide(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            approval_ids=[second.approval_id],
            decision="APPROVED",
            decided_by=fixture.principal_id,
            rationale="batch yes",
            scope_hashes=[digest_second],
            idempotency_key="batch-audit-1",
        )

        rows = await _audit_rows_for(engine, fixture, "approval.decided")
        assert [row["payload"]["decision"] for row in rows] == [
            "REJECTED",
            "APPROVED",
        ]
        assert rows[1]["payload"]["batch_id"] is not None
        await AuditService(engine).verify_chain(tenant_id=fixture.tenant_id)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_approved_row_is_visible_to_a_fresh_engine() -> None:
    """Restart simulation at the persistence layer: a brand-new engine
    (fresh connection pool, like a restarted process) reads the APPROVED
    row and its `require_approved` gate passes -- approvals never live in
    process-local state."""
    writer = new_engine()
    reader = new_engine()
    try:
        fixture = await seed_tenant(writer)
        _missions, mission = await _mission(writer, fixture, slug=_slug("DUR"))
        service = ApprovalService(writer)
        digest = approval_scope_hash(
            approval_type="architecture_change",
            mission_id=mission.mission_id,
            payload={"durability": True},
        )
        requested = await service.request(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            approval_type="architecture_change",
            scope_hash=digest,
            requested_by=fixture.principal_id,
            idempotency_key="dur-req-1",
        )
        await service.batch_decide(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            approval_ids=[requested.approval_id],
            decision="APPROVED",
            decided_by=fixture.principal_id,
            rationale="survives restart",
            scope_hashes=[digest],
            idempotency_key="dur-batch-1",
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


# ---------------------------------------------------------------------------
# Batch decisions: atomicity, refusal, idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_approves_all_members_atomically() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        _missions, mission = await _mission(engine, fixture, slug=_slug("BATCH"))
        service = ApprovalService(engine)
        first = await _pending_approval(
            service, fixture, mission.mission_id, key="batch-a-1", tag="a"
        )
        second = await _pending_approval(
            service, fixture, mission.mission_id, key="batch-a-2", tag="b"
        )
        result = await service.batch_decide(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            approval_ids=[first.approval_id, second.approval_id],
            decision="APPROVED",
            decided_by=fixture.principal_id,
            rationale="clear to proceed",
            scope_hashes=[first.scope_hash, second.scope_hash],
            human_minutes=6.0,
            idempotency_key="batch-ok-1",
        )
        assert result.replayed is False
        assert result.batch_id is not None
        assert [item.status for item in result.approvals] == [
            "APPROVED",
            "APPROVED",
        ]
        for item in result.approvals:
            stored = await service.get_approval(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                approval_id=item.approval_id,
            )
            assert stored.status == "APPROVED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_partial_failure_refuses_the_whole_batch() -> None:
    """One bad member (wrong scope hash) aborts everything: no member's
    decision survives, proving all-or-nothing semantics rather than
    best-effort."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        _missions, mission = await _mission(engine, fixture, slug=_slug("BAD"))
        service = ApprovalService(engine)
        good = await _pending_approval(
            service, fixture, mission.mission_id, key="batch-bad-good", tag="good"
        )
        bad = await _pending_approval(
            service, fixture, mission.mission_id, key="batch-bad-bad", tag="bad"
        )
        wrong_digest = approval_scope_hash(
            approval_type="architecture_change",
            mission_id=mission.mission_id,
            payload={"not-the-bound-plan": True},
        )
        with pytest.raises(DdeError) as captured:
            await service.batch_decide(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                approval_ids=[good.approval_id, bad.approval_id],
                decision="APPROVED",
                decided_by=fixture.principal_id,
                rationale="should not land",
                scope_hashes=[good.scope_hash, wrong_digest],
                idempotency_key="batch-refused-1",
            )
        assert captured.value.error_code == "POLICY_DENIED"

        for item in (good, bad):
            still_open = await service.get_approval(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                approval_id=item.approval_id,
            )
            assert still_open.status in {"REQUESTED", "UNDER_REVIEW"}

        rows = await _audit_rows_for(engine, fixture, "approval.decided")
        assert rows == []

        # The failed command left no ledger trace (its transaction rolled
        # back), so the same key is still first-seen: the human may fix
        # the request and complete it once -- but never twice.
        corrected = await service.batch_decide(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            approval_ids=[good.approval_id, bad.approval_id],
            decision="APPROVED",
            decided_by=fixture.principal_id,
            rationale="retry after failure with correct hashes",
            scope_hashes=[good.scope_hash, bad.scope_hash],
            idempotency_key="batch-refused-1",
        )
        assert corrected.batch_id is not None
        assert [item.status for item in corrected.approvals] == [
            "APPROVED",
            "APPROVED",
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_expired_member_refuses_the_batch() -> None:
    """Expiry is checked per member inside the same transaction; an
    expired member means the whole batch refuses."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        _missions, mission = await _mission(engine, fixture, slug=_slug("EXP"))
        live = ApprovalService(engine)
        backdated_service = ApprovalService(engine, clock=_BackdatedClock())
        fresh = await _pending_approval(
            live, fixture, mission.mission_id, key="batch-exp-fresh", tag="fresh"
        )
        stale = await _pending_approval(
            backdated_service,
            fixture,
            mission.mission_id,
            key="batch-exp-stale",
            tag="stale",
        )
        with pytest.raises(DdeError) as captured:
            await live.batch_decide(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                approval_ids=[fresh.approval_id, stale.approval_id],
                decision="APPROVED",
                decided_by=fixture.principal_id,
                rationale="mixed freshness",
                scope_hashes=[fresh.scope_hash, stale.scope_hash],
            )
        assert captured.value.error_code == "POLICY_DENIED"
        survivor = await live.get_approval(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            approval_id=fresh.approval_id,
        )
        assert survivor.status == "REQUESTED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_batch_decide_replays_the_stored_outcome() -> None:
    """Chapter 12.5: repeating the same batch command returns the first
    call's stored outcome without re-deciding -- statuses, timestamps and
    the batch identity are byte-stable across replays."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        _missions, mission = await _mission(engine, fixture, slug=_slug("RPL"))
        service = ApprovalService(engine)
        only = await _pending_approval(
            service, fixture, mission.mission_id, key="batch-rpl-member", tag="rpl"
        )
        kwargs = {
            "tenant_id": fixture.tenant_id,
            "project_id": fixture.project_id,
            "approval_ids": [only.approval_id],
            "decision": "APPROVED",
            "decided_by": fixture.principal_id,
            "rationale": "once",
            "scope_hashes": [only.scope_hash],
            "idempotency_key": "batch-rpl-1",
        }
        first = await service.batch_decide(**kwargs)
        second = await service.batch_decide(**kwargs)
        assert second.replayed is True
        assert second.batch_id == first.batch_id
        assert [item.approval_id for item in second.approvals] == [
            item.approval_id for item in first.approvals
        ]
        assert [item.decided_at for item in second.approvals] == [
            item.decided_at for item in first.approvals
        ]

        rows = await _audit_rows_for(engine, fixture, "approval.decided")
        assert len(rows) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_batch_decide_validates_its_inputs() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        _missions, mission = await _mission(engine, fixture, slug=_slug("VAL"))
        service = ApprovalService(engine)
        only = await _pending_approval(
            service, fixture, mission.mission_id, key="batch-val-member", tag="val"
        )
        other = await _pending_approval(
            service, fixture, mission.mission_id, key="batch-val-other", tag="val2"
        )
        base = {
            "tenant_id": fixture.tenant_id,
            "project_id": fixture.project_id,
            "decided_by": fixture.principal_id,
            "rationale": "validation",
            "decision": "APPROVED",
        }
        with pytest.raises(DdeError) as empty:
            await service.batch_decide(
                **{**base, "approval_ids": [], "scope_hashes": []}
            )
        assert empty.value.error_code == "POLICY_DENIED"
        with pytest.raises(DdeError) as parallel:
            await service.batch_decide(
                **{
                    **base,
                    "approval_ids": [only.approval_id],
                    "scope_hashes": [only.scope_hash, other.scope_hash],
                }
            )
        assert parallel.value.error_code == "POLICY_DENIED"
        with pytest.raises(DdeError) as duplicate:
            await service.batch_decide(
                **{
                    **base,
                    "approval_ids": [only.approval_id, only.approval_id],
                    "scope_hashes": [only.scope_hash, only.scope_hash],
                }
            )
        assert duplicate.value.error_code == "POLICY_DENIED"
        with pytest.raises(DdeError) as decision:
            await service.batch_decide(
                **{
                    **base,
                    "approval_ids": [only.approval_id],
                    "scope_hashes": [only.scope_hash],
                    "decision": "MAYBE",
                }
            )
        assert decision.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Budget-request workflow: grant / deny lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_request_requires_a_concrete_ceiling() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        _missions, mission = await _mission(engine, fixture, slug=_slug("BGT-V"))
        service = ApprovalService(engine)
        with pytest.raises(DdeError) as captured:
            await service.request_budget_increase(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                mission_id=mission.mission_id,
                requested_by=fixture.principal_id,
                idempotency_key="budget-none-1",
                reason="more please",
            )
        assert captured.value.error_code == "POLICY_DENIED"
        with pytest.raises(DdeError) as no_task:
            await service.request_budget_increase(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                mission_id=mission.mission_id,
                requested_by=fixture.principal_id,
                idempotency_key="budget-notask-1",
                reason="no task named",
                requested_max_tokens=1000,
            )
        assert no_task.value.error_code == "POLICY_DENIED"
        with pytest.raises(DdeError) as no_reason:
            await service.request_budget_increase(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                mission_id=mission.mission_id,
                requested_by=fixture.principal_id,
                idempotency_key="budget-noreason-1",
                reason="   ",
                requested_max_tokens=1000,
                task_id=uuid7(),
            )
        assert no_reason.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_granted_budget_increase_replans_with_raised_ceiling(
    tmp_path: Path,
) -> None:
    """Granting re-plans the task's latest ExecutionPlan with the raised
    ceiling in the SAME transaction as the APPROVED decision. The new
    plan carries the ceiling in its hashed, immutable definition --
    restart-safe by construction, and no ad-hoc DB edit. The plan under
    test is a REAL persisted plan from `ExecutionPlanService.plan`."""
    root = repo_root()
    db_engine = new_engine()
    capped = None
    try:
        capped = await build_capped_plan_fixture(
            db_engine,
            tmp_path,
            mission_slug=_slug("BGT-G"),
            budget=AttemptBudget(max_tokens=100),
        )
        service = ApprovalService(db_engine)
        task_id = capped.task.task_id
        original_plan = capped.plan

        budget_request = await service.request_budget_increase(
            tenant_id=capped.tenant.tenant_id,
            project_id=capped.tenant.project_id,
            mission_id=capped.mission.mission_id,
            requested_by=capped.tenant.principal_id,
            idempotency_key="budget-grant-1",
            reason="task needs a bigger instruction budget",
            requested_max_tokens=original_plan.token_budget[ATTEMPT_MAX_TOKENS_KEY]
            + 500,
            task_id=task_id,
        )
        assert budget_request.approval.status == "REQUESTED"

        decided = await service.decide_budget_increase(
            tenant_id=capped.tenant.tenant_id,
            project_id=capped.tenant.project_id,
            approval_id=budget_request.approval.approval_id,
            decided_by=capped.tenant.principal_id,
            decision="APPROVED",
            rationale="headroom justified",
            human_minutes=4.0,
        )
        assert decided.granted is True
        assert decided.plan is not None
        assert decided.plan.plan_id != original_plan.plan_id
        assert (
            decided.plan.token_budget[ATTEMPT_MAX_TOKENS_KEY]
            == original_plan.token_budget[ATTEMPT_MAX_TOKENS_KEY] + 500
        )
        # The new definition was re-hashed over the raised ceiling...
        expected_hash = plan_hash(
            tenant_id=decided.plan.tenant_id,
            project_id=decided.plan.project_id,
            mission_id=decided.plan.mission_id,
            task_id=decided.plan.task_id,
            route_decision_id=decided.plan.route_decision_id,
            context_package_id=decided.plan.context_package_id,
            worker_profile_id=decided.plan.worker_profile_id,
            execution_environment_id=decided.plan.execution_environment_id,
            workspace_policy=dict(decided.plan.workspace_policy),
            capability_requirements=list(decided.plan.capability_requirements),
            enforcement_tier=decided.plan.enforcement_tier,
            autonomy_level=decided.plan.autonomy_level,
            resource_budget=dict(decided.plan.resource_budget),
            time_budget=dict(decided.plan.time_budget),
            token_budget=dict(decided.plan.token_budget),
            network_policy=dict(decided.plan.network_policy),
            filesystem_policy=dict(decided.plan.filesystem_policy),
            checkpoint_policy=dict(decided.plan.checkpoint_policy),
            retry_policy=dict(decided.plan.retry_policy),
            escalation_policy=dict(decided.plan.escalation_policy),
        )
        assert decided.plan.plan_hash == expected_hash
        # ...and the old plan is untouched history.
        reread_original = await _read_plan(
            db_engine, capped.tenant, original_plan.plan_id
        )
        assert reread_original is not None
        assert reread_original.token_budget == original_plan.token_budget

        # The decision itself is audited like any approval decision.
        rows = await _audit_rows_for(db_engine, capped.tenant, "approval.decided")
        assert len(rows) == 1
        assert rows[0]["payload"]["approval_id"] == str(
            budget_request.approval.approval_id
        )
    finally:
        if capped is not None and capped.workspace.status != "CLEANED_UP":
            await WorkspaceService(db_engine, root=root).cleanup(
                workspace=capped.workspace
            )
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_denied_budget_increase_widens_nothing(tmp_path: Path) -> None:
    root = repo_root()
    db_engine = new_engine()
    capped = None
    try:
        capped = await build_capped_plan_fixture(
            db_engine,
            tmp_path,
            mission_slug=_slug("BGT-D"),
            budget=AttemptBudget(max_tokens=50),
        )
        service = ApprovalService(db_engine)
        original_plan = capped.plan
        budget_request = await service.request_budget_increase(
            tenant_id=capped.tenant.tenant_id,
            project_id=capped.tenant.project_id,
            mission_id=capped.mission.mission_id,
            requested_by=capped.tenant.principal_id,
            idempotency_key="budget-deny-1",
            reason="unbounded ask",
            requested_max_tokens=10**9,
            task_id=capped.task.task_id,
        )
        decided = await service.decide_budget_increase(
            tenant_id=capped.tenant.tenant_id,
            project_id=capped.tenant.project_id,
            approval_id=budget_request.approval.approval_id,
            decided_by=capped.tenant.principal_id,
            decision="REJECTED",
            rationale="ceiling stays",
        )
        assert decided.granted is False
        assert decided.plan is None
        reread = await _read_plan(db_engine, capped.tenant, original_plan.plan_id)
        assert reread is not None
        assert reread.token_budget == original_plan.token_budget
        history = await _plans_for_task(db_engine, capped.tenant, capped.task.task_id)
        assert [plan.plan_id for plan in history] == [original_plan.plan_id]

        rows = await _audit_rows_for(db_engine, capped.tenant, "approval.decided")
        assert len(rows) == 1
        assert rows[0]["payload"]["decision"] == "REJECTED"
    finally:
        if capped is not None and capped.workspace.status != "CLEANED_UP":
            await WorkspaceService(db_engine, root=root).cleanup(
                workspace=capped.workspace
            )
        await db_engine.dispose()


@pytest.mark.asyncio
async def test_budget_request_is_idempotent_per_key() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        _missions, mission = await _mission(engine, fixture, slug=_slug("BGT-I"))
        service = ApprovalService(engine)
        task_id = uuid7()
        kwargs = {
            "tenant_id": fixture.tenant_id,
            "project_id": fixture.project_id,
            "mission_id": mission.mission_id,
            "requested_by": fixture.principal_id,
            "idempotency_key": "budget-rpl-1",
            "reason": "same ask twice",
            "requested_max_tokens": 4000,
            "task_id": task_id,
        }
        first = await service.request_budget_increase(**kwargs)
        second = await service.request_budget_increase(**kwargs)
        assert second.approval.approval_id == first.approval.approval_id
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Fixtures/helpers
# ---------------------------------------------------------------------------


async def _read_plan(engine, fixture, plan_id: UUID):
    from engine.execution.repository import ExecutionPlanRepository

    async with open_uow(engine, fixture) as uow:
        plan = await ExecutionPlanRepository().get_plan(uow.connection, plan_id)
        await uow.commit()
    return plan


async def _plans_for_task(engine, fixture, task_id: UUID):
    from engine.execution.repository import ExecutionPlanRepository

    async with open_uow(engine, fixture) as uow:
        plans = await ExecutionPlanRepository().list_for_task(uow.connection, task_id)
        await uow.commit()
    return plans
