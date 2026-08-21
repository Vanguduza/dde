"""PostgreSQL-backed `engine.recovery.service`: schema, state-transition,
negative and recovery tests (Chapter 19.1) -- DDE-020's ExternalEffect
journal acceptance proof.

Wiring is exercised through the real `WorkerManagerService.invoke_run` /
`ScriptedWorkerAdapter.start` / `IntegrationQueueService.submit` call sites.
`WorkspaceService.snapshot` may still journal a git read as optional extra
audit -- that is not the Chapter 12.4 mutation proof.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.lease_service import CapabilityLeaseService
from engine.context.repo import repo_root
from engine.contracts.external_effect import ExternalEffect
from engine.contracts.worker_run import WorkerRun
from engine.core.errors import DdeError
from engine.events.repository import EventsRepository
from engine.integration.service import IntegrationQueueService
from engine.recovery.scope import GIT_UPDATE_REF_OPERATION, git_ref_resource
from engine.recovery.service import (
    EFFECT_CONFLICT,
    ExternalEffectService,
    ReconciliationOutcome,
)
from engine.truth.db import open_unit_of_work
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import TenantFixture, new_engine
from tests.support.integration_fixtures import advance_task_to_verified
from tests.support.worker_fixtures import WorkerFixture, build_worker_fixture


@dataclass
class JournalFixture:
    tenant: TenantFixture
    worker: WorkerFixture
    run: WorkerRun
    workspaces: WorkspaceService
    manager: WorkerManagerService
    effects: ExternalEffectService
    lease_id: UUID
    engine: AsyncEngine


async def _manager_with_scripted_adapter(
    db_engine: AsyncEngine, workspaces: WorkspaceService
) -> WorkerManagerService:
    leases = CapabilityLeaseService(db_engine)
    registry = WorkerProfileRegistry()
    await registry.register_profile(ScriptedWorkerAdapter(workspaces, leases))
    return WorkerManagerService(db_engine, registry, leases=leases)


async def _journal_fixture(
    engine: AsyncEngine, tmp_path: Path, *, mission_slug: str
) -> JournalFixture:
    """A real completed WorkerRun whose `capability.run_local_process`
    effect is already journaled -- supplies the FK-valid worker_run_id and
    capability_lease_id isolated service tests need."""
    worker = await build_worker_fixture(engine, tmp_path, mission_slug=mission_slug)
    workspaces = WorkspaceService(engine, root=repo_root())
    manager = await _manager_with_scripted_adapter(engine, workspaces)
    run = await manager.invoke_run(
        task=worker.task,
        execution_plan=worker.execution_plan,
        workspace=worker.workspace,
        input_context_hash=worker.context_package.assembly_hash,
        action=WorkerAction(command=[sys.executable, "-c", "pass"]),
        idempotency_key=f"{mission_slug}:invoke",
    )
    effects = workspaces.effects
    journaled = await effects.list_for_run(
        tenant_id=worker.tenant.tenant_id,
        project_id=worker.tenant.project_id,
        worker_run_id=run.run_id,
    )
    assert journaled, "invoke_run must journal capability.run_local_process"
    return JournalFixture(
        tenant=worker.tenant,
        worker=worker,
        run=run,
        workspaces=workspaces,
        manager=manager,
        effects=effects,
        lease_id=journaled[0].capability_lease_id,
        engine=engine,
    )


async def _prepare(
    fixture: JournalFixture,
    *,
    idempotency_key: str,
    side_effect_class: str = "WORKSPACE_LOCAL",
    operation: str = "test-op",
    approval_scope_hash: str | None = None,
) -> ExternalEffect:
    return await fixture.effects.prepare(
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
        mission_id=fixture.worker.mission.mission_id,
        worker_run_id=fixture.run.run_id,
        capability_lease_id=fixture.lease_id,
        target_system="test",
        target_resource="test-resource",
        operation=operation,
        side_effect_class=side_effect_class,
        idempotency_key=idempotency_key,
        approval_scope_hash=approval_scope_hash,
    )


@pytest.mark.asyncio
async def test_schema_round_trip_persists_declared_columns(tmp_path: Path) -> None:
    """A row read back from the real `external_effects` table validates
    against the JSON-schema-generated contract with no drift (Chapter 3.1)."""
    engine = new_engine()
    workspace = None
    try:
        fixture = await _journal_fixture(
            engine, tmp_path, mission_slug="MISSION-EFFECT-SCHEMA"
        )
        workspace = fixture.worker.workspace
        prepared = await _prepare(fixture, idempotency_key="effect-schema-1")
        assert prepared.status == "PREPARED"
        assert prepared.command_id is not None
        assert prepared.request_hash
        assert prepared.confirmed_at is None

        reloaded = await fixture.effects.get_effect(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=prepared.effect_id,
        )
        assert reloaded == prepared
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_state_transition_prepared_sent_confirmed(tmp_path: Path) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture = await _journal_fixture(
            engine, tmp_path, mission_slug="MISSION-EFFECT-CONFIRMED"
        )
        workspace = fixture.worker.workspace
        prepared = await _prepare(fixture, idempotency_key="effect-confirmed-1")
        sent = await fixture.effects.mark_sent(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=prepared.effect_id,
        )
        assert sent.status == "SENT"
        confirmed = await fixture.effects.mark_confirmed(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=prepared.effect_id,
            external_reference="ref-1",
            response_hash="b" * 64,
        )
        assert confirmed.status == "CONFIRMED"
        assert confirmed.external_reference == "ref-1"
        assert confirmed.response_hash == "b" * 64
        assert confirmed.confirmed_at is not None
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_state_transition_sent_failed(tmp_path: Path) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture = await _journal_fixture(
            engine, tmp_path, mission_slug="MISSION-EFFECT-FAILED"
        )
        workspace = fixture.worker.workspace
        prepared = await _prepare(fixture, idempotency_key="effect-failed-1")
        await fixture.effects.mark_sent(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=prepared.effect_id,
        )
        failed = await fixture.effects.mark_failed(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=prepared.effect_id,
            reason="exit_code=1",
        )
        assert failed.status == "FAILED"
        assert failed.confirmed_at is None
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_prepare_is_idempotent_on_the_command_ledger(tmp_path: Path) -> None:
    """A repeated prepare() with the same idempotency_key returns the live
    row (never a second insert) -- including after the row has left
    PREPARED, so snapshot()/start() see the true status (Chapter 12.5)."""
    engine = new_engine()
    workspace = None
    try:
        fixture = await _journal_fixture(
            engine, tmp_path, mission_slug="MISSION-EFFECT-IDEMPOTENT"
        )
        workspace = fixture.worker.workspace
        kwargs = dict(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.worker.mission.mission_id,
            worker_run_id=fixture.run.run_id,
            capability_lease_id=fixture.lease_id,
            target_system="test",
            target_resource="test-resource",
            operation="idempotent-op",
            side_effect_class="WORKSPACE_LOCAL",
            idempotency_key="effect-idempotent-1",
        )
        first = await fixture.effects.prepare(**kwargs)
        second = await fixture.effects.prepare(**kwargs)
        assert second.effect_id == first.effect_id
        assert second.status == "PREPARED"

        await fixture.effects.mark_sent(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=first.effect_id,
        )
        await fixture.effects.mark_confirmed(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=first.effect_id,
        )
        replayed = await fixture.effects.prepare(**kwargs)
        assert replayed.effect_id == first.effect_id
        assert replayed.status == "CONFIRMED"

        listed = await fixture.effects.list_for_run(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            worker_run_id=fixture.run.run_id,
        )
        matching = [row for row in listed if row.effect_id == first.effect_id]
        assert len(matching) == 1
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_cannot_skip_prepared_to_confirmed(tmp_path: Path) -> None:
    engine = new_engine()
    workspace = None
    try:
        fixture = await _journal_fixture(
            engine, tmp_path, mission_slug="MISSION-EFFECT-NEG-SKIP"
        )
        workspace = fixture.worker.workspace
        prepared = await _prepare(fixture, idempotency_key="effect-neg-skip-1")
        with pytest.raises(DdeError) as excinfo:
            await fixture.effects.mark_confirmed(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                effect_id=prepared.effect_id,
            )
        assert excinfo.value.error_code == "VERSION_CONFLICT"
        assert "PREPARED" in excinfo.value.message
        still = await fixture.effects.get_effect(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=prepared.effect_id,
        )
        assert still.status == "PREPARED"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_irreversible_reconciliation_failure_escalates(
    tmp_path: Path,
) -> None:
    """Chapter 12.4: an IRREVERSIBLE effect whose true external state
    cannot be determined raises rather than silently resolving."""
    engine = new_engine()
    workspace = None
    try:
        fixture = await _journal_fixture(
            engine, tmp_path, mission_slug="MISSION-EFFECT-IRREVERSIBLE"
        )
        workspace = fixture.worker.workspace
        from engine.governance.hashing import approval_scope_hash
        from engine.governance.service import ApprovalService

        digest = approval_scope_hash(
            approval_type="irreversible_effect",
            mission_id=fixture.worker.mission.mission_id,
            payload={"operation": "test-op"},
        )
        approvals = ApprovalService(engine)
        requested = await approvals.request(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.worker.mission.mission_id,
            approval_type="irreversible_effect",
            scope_hash=digest,
            requested_by=fixture.tenant.principal_id,
            idempotency_key="effect-irreversible-approval",
        )
        await approvals.decide(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            approval_id=requested.approval_id,
            decision="APPROVED",
            decided_by=fixture.tenant.principal_id,
            rationale="per-invocation",
            scope_hash=digest,
        )
        prepared = await _prepare(
            fixture,
            idempotency_key="effect-irreversible-1",
            side_effect_class="IRREVERSIBLE",
            approval_scope_hash=digest,
        )
        await fixture.effects.mark_sent(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=prepared.effect_id,
        )
        await fixture.effects.mark_unknown(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=prepared.effect_id,
            reason="connection dropped after send",
        )

        async def undeterminable() -> ReconciliationOutcome:
            return ReconciliationOutcome(
                verified=False, present=False, detail="provider status API unreachable"
            )

        with pytest.raises(DdeError) as excinfo:
            await fixture.effects.reconcile(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                effect_id=prepared.effect_id,
                method="provider_status_api",
                resolver=undeterminable,
            )
        assert excinfo.value.error_code == "EFFECT_IRREVERSIBLE"
        stuck = await fixture.effects.get_effect(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=prepared.effect_id,
        )
        assert stuck.status == "RECONCILING"
        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            events = await EventsRepository().list_events_for_aggregate(
                uow.connection, "external_effect", prepared.effect_id
            )
        assert any(
            event.event_type == "ExternalEffectIrreversibleEscalated"
            for event in events
        )
        assert excinfo.value.details is not None
        assert excinfo.value.details.get("escalation") == "human"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_state_transition_unknown_reconciling_reconciled_via_real_timeout(
    tmp_path: Path,
) -> None:
    """A real subprocess.TimeoutExpired (short timeout vs a long sleep)
    is the production UNKNOWN path -- then a genuine read-after-write
    (the sleep never created the marker file) reconciles as verified
    absence, which is the Chapter 12.4 condition that permits retry."""
    engine = new_engine()
    workspace = None
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-EFFECT-TIMEOUT"
        )
        workspace = worker.workspace
        workspaces = WorkspaceService(engine, root=repo_root())
        manager = await _manager_with_scripted_adapter(engine, workspaces)
        marker = "dde-effect-timeout-marker.txt"
        run = await manager.invoke_run(
            task=worker.task,
            execution_plan=worker.execution_plan,
            workspace=worker.workspace,
            input_context_hash=worker.context_package.assembly_hash,
            action=WorkerAction(
                command=[
                    sys.executable,
                    "-c",
                    (
                        "import time, pathlib; time.sleep(30); "
                        "pathlib.Path('dde-effect-timeout-marker.txt').write_text('x')"
                    ),
                ],
                timeout_seconds=0.3,
                expected_artifact=marker,
            ),
            idempotency_key="effect-timeout-invoke-1",
        )
        assert run.status == "FAILED"
        assert run.failure_class == "SIDE_EFFECT_UNKNOWN"

        effects = await workspaces.effects.list_for_run(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
            worker_run_id=run.run_id,
        )
        local = [row for row in effects if row.target_system == "local_process"]
        assert len(local) == 1
        assert local[0].status == "UNKNOWN"

        result = await workspaces.effects.reconcile_journaled(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
            effect_id=local[0].effect_id,
        )
        assert result.effect.status == "RECONCILED"
        assert result.verified_absent is True
        assert result.effect.reconciliation_method == "workspace_artifact_stat"
        assert result.effect.confirmed_at is None
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_end_to_end_invoke_run_journals_real_git_and_process_effects(
    tmp_path: Path,
) -> None:
    """WorkerManagerService.invoke_run journals run_local_process and
    the optional extra git_snapshot read. The Chapter 12.4 git mutation
    proof is IntegrationQueueService.submit's update-ref, tested
    separately."""
    engine = new_engine()
    workspace = None
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-EFFECT-E2E"
        )
        workspace = worker.workspace
        workspaces = WorkspaceService(engine, root=repo_root())
        manager = await _manager_with_scripted_adapter(engine, workspaces)
        run = await manager.invoke_run(
            task=worker.task,
            execution_plan=worker.execution_plan,
            workspace=worker.workspace,
            input_context_hash=worker.context_package.assembly_hash,
            action=WorkerAction(
                command=[sys.executable, "-c", "print('dde-effect-e2e')"],
                write_files={"dde-effect-e2e.txt": b"journaled snapshot\n"},
            ),
            idempotency_key="effect-e2e-invoke-1",
        )
        assert run.status == "COMPLETED"
        effects = await workspaces.effects.list_for_run(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
            worker_run_id=run.run_id,
        )
        by_system = {row.target_system: row for row in effects}
        assert set(by_system) == {"git", "local_process"}
        assert by_system["git"].status == "CONFIRMED"
        assert by_system["git"].operation == "git_snapshot"
        assert by_system["git"].side_effect_class == "EXTERNAL_IDEMPOTENT"
        assert by_system["git"].external_reference
        assert by_system["local_process"].status == "CONFIRMED"
        assert by_system["local_process"].side_effect_class == "WORKSPACE_LOCAL"
        assert by_system["local_process"].response_hash
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


_TIMEOUT_COMMAND = (
    "import time, pathlib; time.sleep(30); "
    "pathlib.Path('dde-effect-timeout-marker.txt').write_text('x')"
)


@pytest.mark.asyncio
async def test_second_invoke_run_refused_while_unknown_then_allowed_after_absence(
    tmp_path: Path,
) -> None:
    """A new WorkerRun / new idempotency key cannot bypass Chapter 12.4
    while UNKNOWN exists; verified-absence reconcile permits a retry."""
    engine = new_engine()
    workspace = None
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-EFFECT-BLOCK-RETRY"
        )
        workspace = worker.workspace
        workspaces = WorkspaceService(engine, root=repo_root())
        manager = await _manager_with_scripted_adapter(engine, workspaces)
        action = WorkerAction(
            command=[sys.executable, "-c", _TIMEOUT_COMMAND],
            timeout_seconds=0.3,
            expected_artifact="dde-effect-timeout-marker.txt",
        )
        first = await manager.invoke_run(
            task=worker.task,
            execution_plan=worker.execution_plan,
            workspace=worker.workspace,
            input_context_hash=worker.context_package.assembly_hash,
            action=action,
            idempotency_key="effect-block-retry-1",
        )
        assert first.failure_class == "SIDE_EFFECT_UNKNOWN"

        with pytest.raises(DdeError) as blocked:
            await manager.invoke_run(
                task=worker.task,
                execution_plan=worker.execution_plan,
                workspace=worker.workspace,
                input_context_hash=worker.context_package.assembly_hash,
                action=action,
                idempotency_key="effect-block-retry-2",
            )
        assert blocked.value.error_code == EFFECT_CONFLICT

        effects = await workspaces.effects.list_unreconciled(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
            mission_id=worker.mission.mission_id,
        )
        unknown = [row for row in effects if row.status == "UNKNOWN"]
        assert len(unknown) == 1
        result = await workspaces.effects.reconcile_journaled(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
            effect_id=unknown[0].effect_id,
        )
        assert result.verified_absent is True

        retry = await manager.invoke_run(
            task=worker.task,
            execution_plan=worker.execution_plan,
            workspace=worker.workspace,
            input_context_hash=worker.context_package.assembly_hash,
            action=action,
            idempotency_key="effect-block-retry-3",
        )
        assert retry.failure_class == "SIDE_EFFECT_UNKNOWN"
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_verified_present_reconcile_does_not_permit_duplicate_mutation(
    tmp_path: Path,
) -> None:
    """Verified presence resolves to RECONCILED with confirmed_at set and
    refuses a second mutation of the same scope."""
    engine = new_engine()
    workspace = None
    try:
        worker = await build_worker_fixture(
            engine, tmp_path, mission_slug="MISSION-EFFECT-PRESENT"
        )
        workspace = worker.workspace
        workspaces = WorkspaceService(engine, root=repo_root())
        manager = await _manager_with_scripted_adapter(engine, workspaces)
        marker = "dde-effect-timeout-marker.txt"
        action = WorkerAction(
            command=[sys.executable, "-c", _TIMEOUT_COMMAND],
            timeout_seconds=0.3,
            expected_artifact=marker,
        )
        run = await manager.invoke_run(
            task=worker.task,
            execution_plan=worker.execution_plan,
            workspace=worker.workspace,
            input_context_hash=worker.context_package.assembly_hash,
            action=action,
            idempotency_key="effect-present-1",
        )
        assert run.failure_class == "SIDE_EFFECT_UNKNOWN"
        root = Path(worker.workspace.workspace_path or "")
        (root / marker).write_text("happened", encoding="utf-8")

        effects = await workspaces.effects.list_for_run(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
            worker_run_id=run.run_id,
        )
        local = [row for row in effects if row.target_system == "local_process"]
        result = await workspaces.effects.reconcile_journaled(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
            effect_id=local[0].effect_id,
        )
        assert result.verified_absent is False
        assert result.effect.status == "RECONCILED"
        assert result.effect.confirmed_at is not None

        with pytest.raises(DdeError) as blocked:
            await manager.invoke_run(
                task=worker.task,
                execution_plan=worker.execution_plan,
                workspace=worker.workspace,
                input_context_hash=worker.context_package.assembly_hash,
                action=action,
                idempotency_key="effect-present-2",
            )
        assert blocked.value.error_code == EFFECT_CONFLICT
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_abandon_sent_moves_crash_abandoned_row_to_unknown(
    tmp_path: Path,
) -> None:
    """Chapter 12.4 SENT -> UNKNOWN: production recovery can mark a
    crash-abandoned SENT row unknown, after which the scope is blocked
    until reconcile."""
    engine = new_engine()
    workspace = None
    try:
        fixture = await _journal_fixture(
            engine, tmp_path, mission_slug="MISSION-EFFECT-ABANDON"
        )
        workspace = fixture.worker.workspace
        prepared = await _prepare(fixture, idempotency_key="effect-abandon-1")
        await fixture.effects.mark_sent(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=prepared.effect_id,
        )
        abandoned = await fixture.effects.abandon_sent(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=prepared.effect_id,
            reason="process crashed after mark_sent with no observed outcome",
        )
        assert abandoned.status == "UNKNOWN"
        with pytest.raises(DdeError) as excinfo:
            await fixture.effects.abandon_sent(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                effect_id=prepared.effect_id,
                reason="already unknown",
            )
        assert excinfo.value.error_code == "VERSION_CONFLICT"
        listed = await fixture.effects.list_unreconciled(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            mission_id=fixture.worker.mission.mission_id,
        )
        assert any(row.effect_id == abandoned.effect_id for row in listed)
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=repo_root()).cleanup(
                workspace=workspace
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_git_update_ref_is_journaled_and_blocked_while_unknown(
    tmp_path: Path,
) -> None:
    """A real git mutation (submit's update-ref) is journaled. A second
    attempt is refused while UNKNOWN; verified-absence reconcile permits
    the publish."""
    engine = new_engine()
    root = repo_root()
    workspace = None
    task_branch = None
    mission_branch = None
    try:
        from engine.integration import git as integration_git
        from engine.workers.repository import WorkerRunRepository
        from tests.support.execution_fixtures import build_execution_fixture

        execution = await build_execution_fixture(
            engine,
            tmp_path,
            mission_slug="MISSION-EFFECT-GIT-MUT",
            task_class="verification",
        )
        advanced = await advance_task_to_verified(
            engine,
            tmp_path,
            tenant=execution.tenant,
            task=execution.task,
            context_package=execution.context_package,
            route_decision=execution.route_decision,
            write_files={
                "engine/routing/dde020-git-mutation.txt": b"git mutation proof\n"
            },
            idempotency_prefix="effect-git-mut",
        )
        workspace = advanced.workspace
        task_branch = f"task/{advanced.task.task_id}-a"
        mission_branch = f"mission/{advanced.task.mission_id}"
        ref = git_ref_resource(task_branch)

        async with open_unit_of_work(
            engine,
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
        ) as uow:
            runs = await WorkerRunRepository().list_for_attempt(
                uow.connection, advanced.task_attempt_id
            )
        assert runs
        run = runs[-1]
        effects = ExternalEffectService(engine)
        journaled = await effects.list_for_run(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            worker_run_id=run.run_id,
        )
        lease_id = journaled[0].capability_lease_id
        prepared = await effects.prepare(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            mission_id=advanced.task.mission_id,
            worker_run_id=run.run_id,
            capability_lease_id=lease_id,
            target_system="git",
            target_resource=ref,
            operation=GIT_UPDATE_REF_OPERATION,
            side_effect_class="EXTERNAL_IDEMPOTENT",
            idempotency_key="effect-git-mut-unknown",
            evidence_ref=ref,
        )
        await effects.mark_sent(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            effect_id=prepared.effect_id,
        )
        await effects.abandon_sent(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            effect_id=prepared.effect_id,
            reason="simulated crash after SENT before update-ref",
        )

        queue = IntegrationQueueService(engine, root=root)
        with pytest.raises(DdeError) as blocked:
            await queue.submit(
                tenant_id=advanced.task.tenant_id,
                project_id=advanced.task.project_id,
                mission_id=advanced.task.mission_id,
                task_id=advanced.task.task_id,
                task_attempt_id=advanced.task_attempt_id,
                workspace=advanced.workspace,
                lease=advanced.lease,
                verification_run_id=advanced.verification_run.verification_run_id,
                attempt_label="a",
            )
        assert blocked.value.error_code == EFFECT_CONFLICT

        result = await effects.reconcile_journaled(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            effect_id=prepared.effect_id,
            repo_root=root,
        )
        assert result.verified_absent is True

        proposal = await queue.submit(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            mission_id=advanced.task.mission_id,
            task_id=advanced.task.task_id,
            task_attempt_id=advanced.task_attempt_id,
            workspace=advanced.workspace,
            lease=advanced.lease,
            verification_run_id=advanced.verification_run.verification_run_id,
            attempt_label="a",
        )
        assert proposal.status == "QUEUED"
        published = await effects.list_for_run(
            tenant_id=advanced.task.tenant_id,
            project_id=advanced.task.project_id,
            worker_run_id=run.run_id,
        )
        mut = [
            row
            for row in published
            if row.operation == GIT_UPDATE_REF_OPERATION and row.status == "CONFIRMED"
        ]
        assert mut
        assert mut[0].side_effect_class == "EXTERNAL_IDEMPOTENT"
        assert mut[0].external_reference
        assert mut[0].target_resource == ref
    finally:
        if workspace is not None:
            await WorkspaceService(engine, root=root).cleanup(workspace=workspace)
        if task_branch is not None:
            from engine.integration import git as integration_git

            integration_git.delete_branch(root, task_branch)
        if mission_branch is not None:
            from engine.integration import git as integration_git

            integration_git.delete_branch(root, mission_branch)
        await engine.dispose()
