"""PostgreSQL-backed `engine.recovery.service`: schema, state-transition,
negative and recovery tests (Chapter 19.1) -- DDE-020's ExternalEffect
journal acceptance proof.

Wiring is exercised through the real `WorkerManagerService.invoke_run` /
`ScriptedWorkerAdapter.start` / `WorkspaceService.snapshot` call sites, not
a parallel unused helper -- unlike DDE-019's broker, this journal has
genuine side-effecting callers.
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
from engine.recovery.service import (
    ExternalEffectService,
    ReconciliationOutcome,
)
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.scripted_adapter import ScriptedWorkerAdapter
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import TenantFixture, new_engine
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
        prepared = await _prepare(
            fixture,
            idempotency_key="effect-irreversible-1",
            side_effect_class="IRREVERSIBLE",
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
        assert excinfo.value.error_code == "EFFECT_UNKNOWN"
        stuck = await fixture.effects.get_effect(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            effect_id=prepared.effect_id,
        )
        assert stuck.status == "RECONCILING"
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
            ),
            idempotency_key="effect-timeout-invoke-1",
        )
        assert run.status == "FAILED"
        assert run.failure_class == "WORKER_COMMAND_TIMEOUT"

        effects = await workspaces.effects.list_for_run(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
            worker_run_id=run.run_id,
        )
        local = [row for row in effects if row.target_system == "local_process"]
        assert len(local) == 1
        assert local[0].status == "UNKNOWN"

        root = Path(worker.workspace.workspace_path or "")

        async def marker_absent() -> ReconciliationOutcome:
            present = (root / marker).exists()
            return ReconciliationOutcome(
                verified=True,
                present=present,
                detail="workspace marker file after killed sleep",
            )

        result = await workspaces.effects.reconcile(
            tenant_id=worker.tenant.tenant_id,
            project_id=worker.tenant.project_id,
            effect_id=local[0].effect_id,
            method="workspace_marker_stat",
            resolver=marker_absent,
        )
        assert result.effect.status == "RECONCILED"
        assert result.verified_absent is True
        assert result.effect.reconciliation_method == "workspace_marker_stat"
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
    """WorkerManagerService.invoke_run through ScriptedWorkerAdapter
    journals both real call sites: git snapshot and local-process execute."""
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
