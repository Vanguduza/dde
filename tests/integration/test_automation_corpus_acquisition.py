"""Governed EDR-0018 acquisition certification against PostgreSQL."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from engine.contracts.worker_run import WorkerRun
from engine.core.clock import SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.execution.service import ExecutionPlanService
from engine.object_store.durable import LocalScopedObjectStore
from engine.source.acquisition import (
    CAPABILITY_AUTOMATION_CORPUS,
    AutomationCorpusAcquisitionService,
)
from engine.source.automation import exact_snapshot_url
from engine.source.repository import SourceRepository
from engine.truth.db import open_unit_of_work
from tests.support.capability_fixtures import ensure_capabilities_seeded
from tests.support.db import new_engine
from tests.support.execution_fixtures import build_execution_fixture

pytestmark = pytest.mark.integration

MIT = """MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the \"Software\"), to deal
in the Software without restriction.
"""


def _archive(*, licensed: bool = True) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if licensed:
            zf.writestr("n8n-workflows/LICENSE", MIT)
        zf.writestr(
            "n8n-workflows/workflows/example.json",
            json.dumps(
                {
                    "name": "Webhook to HTTP",
                    "nodes": [
                        {"name": "Webhook", "type": "n8n-nodes-base.webhook"},
                        {
                            "name": "HTTP",
                            "type": "n8n-nodes-base.httpRequest",
                            "parameters": {"url": "https://example.invalid"},
                        },
                    ],
                    "connections": {},
                }
            ),
        )
    return stream.getvalue()


async def _target_plan(engine, tmp_path: Path, *, slug: str):
    fixture = await build_execution_fixture(
        engine,
        tmp_path,
        mission_slug=slug,
        task_class="verification",
    )
    await ensure_capabilities_seeded(
        engine,
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
    )
    async with open_unit_of_work(
        engine,
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
    ) as uow:
        await uow.connection.execute(
            text("UPDATE projects SET kind='TARGET_APPLICATION' WHERE project_id=:p"),
            {"p": fixture.tenant.project_id},
        )
        await uow.commit()
    plans = ExecutionPlanService(engine)
    plan = await plans.plan(
        task=fixture.task,
        route_decision=fixture.route_decision,
        context_package_id=fixture.context_package.package_id,
    )
    now = SystemClock().now()
    run = WorkerRun(
        run_id=uuid7(),
        tenant_id=fixture.tenant.tenant_id,
        project_id=fixture.tenant.project_id,
        mission_id=fixture.mission.mission_id,
        task_attempt_id=uuid7(),
        sequence=1,
        execution_plan_id=plan.plan_id,
        worker_id="worker.scripted-deterministic-v1",
        worker_profile_id="profile.deterministic_runner",
        environment_id=plan.execution_environment_id,
        workspace_id=uuid7(),
        context_package_id=plan.context_package_id,
        policy_version="test",
        lease_set_hash="test",
        status="RUNNING",
        created_at=now,
        updated_at=now,
    )
    return fixture, run


@pytest.mark.asyncio
async def test_acquisition_is_lease_effect_bound_quarantined_and_idempotent(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        fixture, worker_run = await _target_plan(
            engine,
            tmp_path,
            slug=f"MISSION-AUTOMATION-ACQUIRE-{uuid4().hex}",
        )
        commit_sha = "a" * 40
        archive = _archive()
        fetch_calls: list[str] = []

        async def fetch(uri: str) -> bytes:
            assert uri == exact_snapshot_url(commit_sha)
            async with open_unit_of_work(
                engine,
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
            ) as uow:
                lease = await uow.connection.execute(
                    text(
                        "SELECT status FROM capability_leases "
                        "WHERE worker_run_id=:run AND capability_id=:capability"
                    ),
                    {
                        "run": worker_run.run_id,
                        "capability": CAPABILITY_AUTOMATION_CORPUS,
                    },
                )
                assert lease.scalar_one() == "GRANTED"
                effect = await uow.connection.execute(
                    text(
                        "SELECT status FROM external_effects "
                        "WHERE worker_run_id=:run AND target_resource=:uri"
                    ),
                    {"run": worker_run.run_id, "uri": uri},
                )
                assert effect.scalar_one() == "SENT"
            fetch_calls.append(uri)
            return archive

        store = LocalScopedObjectStore(
            namespace="automation-corpus",
            root=tmp_path / "objects",
        )
        service = AutomationCorpusAcquisitionService(
            engine,
            object_store=store,
            fetch=fetch,
        )
        first = await service.acquire_snapshot(
            worker_run=worker_run,
            commit_sha=commit_sha,
            idempotency_key=f"acquire:{commit_sha}",
        )
        assert first.state == "QUARANTINED"
        assert first.license_state == "VERIFIED"
        assert first.workflow_count == 1
        assert fetch_calls == [exact_snapshot_url(commit_sha)]
        assert first.object_ref.startswith(
            f"automation-corpus/{fixture.tenant.tenant_id}/{fixture.tenant.project_id}/"
        )
        assert (
            store.read(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                key=first.object_ref,
            )
            == archive
        )

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            artifact = await SourceRepository().get_artifact(
                uow.connection,
                artifact_id=first.artifact_id,
            )
            assert artifact is not None
            admission = await SourceRepository().latest_admission(
                uow.connection,
                artifact_id=first.artifact_id,
            )
            assert admission is not None
            assert admission.state == "QUARANTINED"
            assert admission.sanitization_state == "NOT_STARTED"
            effect = await uow.connection.execute(
                text("SELECT status FROM external_effects WHERE effect_id=:effect_id"),
                {"effect_id": first.acquisition_effect_id},
            )
            assert effect.scalar_one() == "CONFIRMED"

        second = await service.acquire_snapshot(
            worker_run=worker_run,
            commit_sha=commit_sha,
            idempotency_key=f"acquire-again:{commit_sha}",
        )
        assert second.snapshot_id == first.snapshot_id
        assert fetch_calls == [exact_snapshot_url(commit_sha)]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_control_plane_is_refused_before_lease_or_network(tmp_path: Path) -> None:
    engine = new_engine()
    try:
        fixture, worker_run = await _target_plan(
            engine,
            tmp_path,
            slug=f"MISSION-AUTOMATION-CONTROL-PLANE-{uuid4().hex}",
        )
        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            await uow.connection.execute(
                text(
                    "UPDATE projects SET kind='DDE_CONTROL_PLANE' WHERE project_id=:p"
                ),
                {"p": fixture.tenant.project_id},
            )
            await uow.commit()

        fetched = False

        async def forbidden_fetch(_uri: str) -> bytes:
            nonlocal fetched
            fetched = True
            raise AssertionError("network fetch must not run for DDE_CONTROL_PLANE")

        service = AutomationCorpusAcquisitionService(
            engine,
            object_store=LocalScopedObjectStore(
                namespace="automation-corpus",
                root=tmp_path / "objects-control",
            ),
            fetch=forbidden_fetch,
        )
        with pytest.raises(DdeError) as excinfo:
            await service.acquire_snapshot(
                worker_run=worker_run,
                commit_sha="b" * 40,
                idempotency_key="control-plane-refusal",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
        assert fetched is False
        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            lease_count = await uow.connection.execute(
                text(
                    "SELECT count(*) FROM capability_leases "
                    "WHERE worker_run_id=:run AND capability_id=:capability"
                ),
                {
                    "run": worker_run.run_id,
                    "capability": CAPABILITY_AUTOMATION_CORPUS,
                },
            )
            assert lease_count.scalar_one() == 0
    finally:
        await engine.dispose()
