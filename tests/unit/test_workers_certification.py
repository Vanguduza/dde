"""Chapter 8.5 smoke runner and WorkerProfileRegistry STALE gating."""

from __future__ import annotations

import pytest

from adapters.cursor.adapter import AUTO_CREATE_PR, CursorWorkerAdapter
from engine.contracts.worker_run import WorkerRun
from engine.core.errors import DdeError
from engine.workers.adapter import UsageRecord
from engine.workers.certification import SMOKE_FIXTURE_IDS
from engine.workers.registry import WorkerProfileRegistry
from engine.workers.smoke import run_smoke


@pytest.mark.asyncio
async def test_cursor_adapter_smoke_passes_without_a_vendor_sdk() -> None:
    adapter = CursorWorkerAdapter()
    report = await run_smoke(adapter)
    assert report.passed is True
    assert report.fixture_ids == SMOKE_FIXTURE_IDS
    assert report.cost_usd == 0.0
    assert AUTO_CREATE_PR is False


@pytest.mark.asyncio
async def test_cursor_start_fail_closes_without_fabricating_a_run() -> None:
    adapter = CursorWorkerAdapter()
    registration = await adapter.register()
    assert registration.worker_profile_id == "profile.general_implementation"
    from datetime import UTC, datetime
    from uuid import uuid4

    from engine.contracts.worker_run import WorkerRun

    now = datetime.now(UTC)
    run = WorkerRun(
        run_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        mission_id=uuid4(),
        task_attempt_id=uuid4(),
        sequence=1,
        execution_plan_id=uuid4(),
        worker_id=registration.worker_id,
        worker_profile_id=registration.worker_profile_id,
        environment_id=uuid4(),
        workspace_id=uuid4(),
        context_package_id=uuid4(),
        policy_version="t",
        lease_set_hash="t",
        status="RUNNING",
        created_at=now,
        updated_at=now,
    )
    with pytest.raises(DdeError) as captured:
        await adapter.start(run)
    assert captured.value.error_code == "POLICY_DENIED"
    assert "cursor_sdk" in captured.value.message


@pytest.mark.asyncio
async def test_smoke_usd_ceiling_is_enforced() -> None:
    class _Expensive(CursorWorkerAdapter):
        async def collect_usage(self, worker_run: WorkerRun) -> UsageRecord:
            del worker_run
            return UsageRecord(duration_ms=0, cost_usd=6.0)

    with pytest.raises(DdeError) as captured:
        await run_smoke(_Expensive(), max_usd=5.0)
    assert captured.value.error_code == "BUDGET_EXCEEDED"


@pytest.mark.asyncio
async def test_stale_profile_is_refused_outside_development() -> None:
    registry = WorkerProfileRegistry()
    adapter = CursorWorkerAdapter()
    recorded = await registry.register_profile(adapter)
    assert recorded.status == "STALE"
    registry.get_certified_adapter(
        recorded.registration.worker_profile_id, environment_class="development"
    )
    with pytest.raises(DdeError) as captured:
        registry.get_certified_adapter(
            recorded.registration.worker_profile_id,
            environment_class="production",
        )
    assert captured.value.error_code == "PROFILE_STALE"
    report = await run_smoke(adapter)
    registry.record_smoke_pass(report.profile_id, report.profile_hash)
    certified = registry.get_certified_adapter(
        report.profile_id, environment_class="production"
    )
    assert certified is adapter
