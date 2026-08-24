"""DDE-045 capability.security / security_scan proofs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.security.adapter import SecurityWorkerAdapter
from adapters.security.sast import InProcessSecurityScanner
from engine.capabilities.lease_service import CapabilityLeaseService
from engine.capabilities.security import SecurityScanSpec
from engine.capabilities.seed import SEED_CAPABILITIES, seed_capabilities
from engine.capabilities.service import CapabilityRegistryService
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.verification.checks import CheckSpec, run_check
from engine.verification.oracle import EXECUTABLE_KINDS, validate_definition
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.service import WorkerManagerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine, seed_tenant
from tests.support.worker_fixtures import build_worker_fixture


def test_security_scan_is_executable_oracle_kind() -> None:
    assert "security_scan" in EXECUTABLE_KINDS
    validate_definition(
        scope="task",
        observable_outcomes=[
            CheckSpec(
                outcome_id=uuid7(),
                statement="workspace has no planted secrets",
                kind="security_scan",
                ref="security:sast",
                command=["sast"],
            )
        ],
        negative_cases=[],
        minimum_confidence=1.0,
    )


def test_capability_security_is_in_seed_portfolio() -> None:
    ids = {spec.capability_id for spec in SEED_CAPABILITIES}
    assert "capability.security" in ids
    security = next(
        s for s in SEED_CAPABILITIES if s.capability_id == "capability.security"
    )
    assert security.side_effect_class == "PURE_READ"
    assert security.enforcement_tier == "T1"


@pytest.mark.asyncio
async def test_security_smoke_fail_closes_without_fabricating_success() -> None:
    from engine.workers.smoke import run_smoke

    report = await run_smoke(SecurityWorkerAdapter())
    assert report.passed is True
    assert report.profile_id == "profile.security"


@pytest.mark.asyncio
async def test_sast_refuses_dast_and_agentic_modes() -> None:
    scanner = InProcessSecurityScanner()
    with pytest.raises(DdeError) as exc:
        await scanner.scan(SecurityScanSpec(root=".", mode="dast"))
    assert exc.value.error_code == "POLICY_DENIED"
    with pytest.raises(DdeError) as exc2:
        await scanner.scan(SecurityScanSpec(root=".", mode="agentic"))
    assert exc2.value.error_code == "POLICY_DENIED"


@pytest.mark.asyncio
async def test_sast_passes_clean_workspace(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text("print('hello')\n", encoding="utf-8")
    scanner = InProcessSecurityScanner()
    result = await scanner.scan(SecurityScanSpec(root=str(tmp_path), mode="sast"))
    assert result.passed is True
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_sast_fails_on_planted_secret(tmp_path: Path) -> None:
    (tmp_path / "leak.py").write_text(
        'KEY = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8"
    )
    scanner = InProcessSecurityScanner()
    result = await scanner.scan(SecurityScanSpec(root=str(tmp_path), mode="sast"))
    assert result.passed is False
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["secret_detection"]["passed"] is False


@pytest.mark.asyncio
async def test_seed_registers_capability_security() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = CapabilityRegistryService(engine)
        registered = await seed_capabilities(
            service, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        )
        assert "capability.security" in {item.capability_id for item in registered}
        active = await service.get_active(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id="capability.security",
        )
        assert active.side_effect_class == "PURE_READ"
    finally:
        await engine.dispose()


def _workspace(tmp_path: Path) -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        workspace_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        mission_id=uuid7(),
        task_id=uuid7(),
        execution_environment_id=uuid7(),
        base_revision="HEAD",
        current_revision="HEAD",
        workspace_path=str(tmp_path),
        policy={},
        status="READY",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_security_scan_check_uses_injected_scanner(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    result = await run_check(
        workspaces=None,  # type: ignore[arg-type]
        workspace=_workspace(tmp_path),
        spec=CheckSpec(
            outcome_id=uuid7(),
            statement="clean",
            kind="security_scan",
            ref="security:sast",
            command=["sast"],
        ),
        security=InProcessSecurityScanner(),
    )
    assert result.status == "PASSED"


@pytest.mark.asyncio
async def test_invoke_run_security_scan_grants_lease(tmp_path: Path) -> None:
    root = Path.cwd()
    db_engine = new_engine()
    try:
        fixture = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-SECURITY-SCAN"
        )
        workspaces = WorkspaceService(db_engine, root=root)
        leases = CapabilityLeaseService(db_engine)
        registry = WorkerProfileRegistry()

        class _AlwaysPass:
            async def scan(self, spec: SecurityScanSpec):
                from engine.capabilities.security import SecurityScanResult

                del spec
                return SecurityScanResult(
                    exit_code=0,
                    stdout='{"mode":"sast","passed":true}',
                    stderr="",
                    duration_ms=1,
                    timed_out=False,
                    passed=True,
                )

        adapter = SecurityWorkerAdapter(
            workspaces,
            leases,
            scanner=_AlwaysPass(),  # type: ignore[arg-type]
        )
        await registry.register_profile(adapter)
        manager = WorkerManagerService(db_engine, registry, leases=leases)
        plan = fixture.execution_plan.model_copy(
            update={"worker_profile_id": "profile.security"}
        )
        run = await manager.invoke_run(
            task=fixture.task,
            execution_plan=plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=WorkerAction(command=(), security_mode="sast"),
            idempotency_key="security-scan-run-1",
        )
        assert run.status == "COMPLETED", (run.status, run.failure_class)
    finally:
        await db_engine.dispose()
