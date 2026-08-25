"""DDE-048 capability.android_analysis / android_scan proofs."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.android.adapter import AndroidWorkerAdapter
from adapters.android.static import InProcessAndroidAnalyzer
from engine.capabilities.android import AndroidScanSpec
from engine.capabilities.lease_service import CapabilityLeaseService
from engine.capabilities.seed import SEED_CAPABILITIES, seed_capabilities
from engine.capabilities.service import CapabilityRegistryService
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.routing.policy import (
    CAPABILITY_ANDROID,
    PROFILE_ANDROID,
    WORKLOAD_CLASSES,
)
from engine.routing.registry import PROFILES
from engine.verification.checks import CheckSpec, run_check
from engine.verification.oracle import EXECUTABLE_KINDS, validate_definition
from engine.workers.adapter import WorkerAction
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.service import WorkerManagerService
from engine.workers.smoke import run_smoke
from engine.workspaces.service import WorkspaceService
from tests.support.db import new_engine, seed_tenant
from tests.support.worker_fixtures import build_worker_fixture


def _apk_bytes(
    *,
    manifest_extra: str = "",
    assets: dict[str, str] | None = None,
    libs: tuple[str, ...] = (),
) -> bytes:
    """Build a minimal-but-real APK-shaped ZIP. The manifest is binary XML
    (AXML) in production; its permission names survive in the string pool,
    which the analyzer must find without a vendor tool."""
    manifest_text = (
        '<manifest package="com.example.app">'
        '<uses-permission android:name="android.permission.INTERNET"/>'
        f"{manifest_extra}</manifest>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as apk:
        apk.writestr("AndroidManifest.xml", manifest_text.encode("utf-16-le"))
        apk.writestr("classes.dex", b"dex\n035\0\0\0")
        apk.writestr("META-INF/CERT.SF", "certificate\n")
        apk.writestr("res/values/strings.xml", "<resources/>")
        for name, content in (assets or {}).items():
            apk.writestr(name, content)
        for abi in libs:
            apk.writestr(f"lib/{abi}/libapp.so", b"\x7fELF")
    return buf.getvalue()


def test_android_scan_is_executable_oracle_kind() -> None:
    assert "android_scan" in EXECUTABLE_KINDS
    validate_definition(
        scope="task",
        observable_outcomes=[
            CheckSpec(
                outcome_id=uuid7(),
                statement="APK requests no undeclared dangerous permission",
                kind="android_scan",
                ref="android:static",
                command=["static"],
            )
        ],
        negative_cases=[],
        minimum_confidence=1.0,
    )


def test_capability_android_is_in_seed_portfolio() -> None:
    ids = {spec.capability_id for spec in SEED_CAPABILITIES}
    assert CAPABILITY_ANDROID in ids
    android = next(
        s for s in SEED_CAPABILITIES if s.capability_id == CAPABILITY_ANDROID
    )
    assert android.side_effect_class == "PURE_READ"
    assert android.enforcement_tier == "T1"


def test_android_profile_declares_capability() -> None:
    assert PROFILE_ANDROID in PROFILES
    assert CAPABILITY_ANDROID in PROFILES[PROFILE_ANDROID].capabilities


def test_android_capability_not_required_by_existing_workloads() -> None:
    for policy in WORKLOAD_CLASSES.values():
        assert CAPABILITY_ANDROID not in policy.require


@pytest.mark.asyncio
async def test_analyzer_refuses_dynamic_modes() -> None:
    analyzer = InProcessAndroidAnalyzer()
    for mode in ("dynamic", "adb", "instrumentation"):
        with pytest.raises(DdeError) as exc:
            await analyzer.scan(AndroidScanSpec(root=".", mode=mode))
        assert exc.value.error_code == "POLICY_DENIED"


@pytest.mark.asyncio
async def test_static_scan_passes_clean_apk(tmp_path: Path) -> None:
    (tmp_path / "app.apk").write_bytes(_apk_bytes())
    result = await InProcessAndroidAnalyzer().scan(
        AndroidScanSpec(root=str(tmp_path), mode="static")
    )
    assert result.passed is True
    payload = json.loads(result.stdout)
    assert payload["mode"] == "static"
    assert payload["apk"]["permissions"] == ["android.permission.INTERNET"]
    assert payload["passed"] is True


@pytest.mark.asyncio
async def test_static_scan_blocks_dangerous_permission(tmp_path: Path) -> None:
    (tmp_path / "app.apk").write_bytes(
        _apk_bytes(
            manifest_extra=(
                '<uses-permission android:name="android.permission.READ_CONTACTS"/>'
            )
        )
    )
    result = await InProcessAndroidAnalyzer().scan(
        AndroidScanSpec(root=str(tmp_path), mode="static")
    )
    assert result.passed is False
    payload = json.loads(result.stdout)
    assert "dangerous_permission:READ_CONTACTS" in payload["blocking"]


@pytest.mark.asyncio
async def test_static_scan_finds_secret_in_asset(tmp_path: Path) -> None:
    (tmp_path / "app.apk").write_bytes(
        _apk_bytes(
            assets={"assets/config.properties": "aws_key=AKIAIOSFODNN7EXAMPLE\n"}
        )
    )
    result = await InProcessAndroidAnalyzer().scan(
        AndroidScanSpec(root=str(tmp_path), mode="static")
    )
    assert result.passed is False
    payload = json.loads(result.stdout)
    assert payload["secret_detection"]["passed"] is False


@pytest.mark.asyncio
async def test_static_scan_reports_native_lib_abis(tmp_path: Path) -> None:
    (tmp_path / "app.apk").write_bytes(_apk_bytes(libs=("arm64-v8a", "armeabi-v7a")))
    result = await InProcessAndroidAnalyzer().scan(
        AndroidScanSpec(root=str(tmp_path), mode="static")
    )
    payload = json.loads(result.stdout)
    assert sorted(payload["apk"]["native_abi"]) == ["arm64-v8a", "armeabi-v7a"]


@pytest.mark.asyncio
async def test_static_scan_requires_an_apk_in_workspace(tmp_path: Path) -> None:
    with pytest.raises(DdeError) as exc:
        await InProcessAndroidAnalyzer().scan(
            AndroidScanSpec(root=str(tmp_path), mode="static")
        )
    assert exc.value.error_code == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_android_smoke_fail_closes_without_fabricating_success() -> None:
    report = await run_smoke(AndroidWorkerAdapter())
    assert report.passed is True
    assert report.profile_id == PROFILE_ANDROID


@pytest.mark.asyncio
async def test_seed_registers_capability_android() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = CapabilityRegistryService(engine)
        registered = await seed_capabilities(
            service, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        )
        assert CAPABILITY_ANDROID in {item.capability_id for item in registered}
        active = await service.get_active(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id=CAPABILITY_ANDROID,
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
async def test_android_scan_check_uses_injected_analyzer(tmp_path: Path) -> None:
    (tmp_path / "app.apk").write_bytes(_apk_bytes())
    result = await run_check(
        workspaces=None,  # type: ignore[arg-type]
        workspace=_workspace(tmp_path),
        spec=CheckSpec(
            outcome_id=uuid7(),
            statement="clean",
            kind="android_scan",
            ref="android:static",
            command=["static"],
        ),
        android=InProcessAndroidAnalyzer(),
    )
    assert result.status == "PASSED"


@pytest.mark.asyncio
async def test_invoke_run_android_scan_grants_lease(tmp_path: Path) -> None:
    root = Path.cwd()
    db_engine = new_engine()
    try:
        fixture = await build_worker_fixture(
            db_engine, tmp_path, mission_slug="MISSION-ANDROID-SCAN"
        )
        workspaces = WorkspaceService(db_engine, root=root)
        leases = CapabilityLeaseService(db_engine)
        registry = WorkerProfileRegistry()

        class _AlwaysPass:
            async def scan(self, spec: AndroidScanSpec):
                from engine.capabilities.android import AndroidScanResult

                del spec
                return AndroidScanResult(
                    exit_code=0,
                    stdout='{"mode":"static","passed":true}',
                    stderr="",
                    duration_ms=1,
                    timed_out=False,
                    passed=True,
                )

        adapter = AndroidWorkerAdapter(
            workspaces,
            leases,
            analyzer=_AlwaysPass(),  # type: ignore[arg-type]
        )
        await registry.register_profile(adapter)
        manager = WorkerManagerService(db_engine, registry, leases=leases)
        plan = fixture.execution_plan.model_copy(
            update={"worker_profile_id": PROFILE_ANDROID}
        )
        run = await manager.invoke_run(
            task=fixture.task,
            execution_plan=plan,
            workspace=fixture.workspace,
            input_context_hash=fixture.context_package.assembly_hash,
            action=WorkerAction(command=(), android_mode="static"),
            idempotency_key="android-scan-run-1",
        )
        assert run.status == "COMPLETED", (run.status, run.failure_class)
    finally:
        await db_engine.dispose()
