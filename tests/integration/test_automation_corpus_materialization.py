"""Certify PostgreSQL raw-quarantine to descriptor materialization."""

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
from engine.core.ids import uuid7
from engine.execution.service import ExecutionPlanService
from engine.object_store.durable import LocalScopedObjectStore
from engine.source.acquisition import AutomationCorpusAcquisitionService
from engine.source.materialization import AutomationCorpusMaterializationService
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


def _workflow_archive() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("repo/LICENSE", MIT)
        zf.writestr(
            "repo/positive.json",
            json.dumps(
                {
                    "name": "Webhook delivery",
                    "nodes": [
                        {"name": "Webhook", "type": "n8n-nodes-base.webhook"},
                        {"name": "HTTP", "type": "n8n-nodes-base.httpRequest"},
                    ],
                    "connections": {},
                }
            ),
        )
        zf.writestr(
            "repo/anti-code.json",
            json.dumps(
                {
                    "name": "Unsafe shell donor",
                    "nodes": [
                        {
                            "name": "Execute",
                            "type": "n8n-nodes-base.executeCommand",
                            "parameters": {"command": "echo never-executed"},
                        }
                    ],
                    "connections": {},
                }
            ),
        )
        zf.writestr(
            "repo/blocked-secret.json",
            json.dumps(
                {
                    "name": "Secret donor",
                    "nodes": [
                        {
                            "name": "HTTP",
                            "type": "n8n-nodes-base.httpRequest",
                            "parameters": {"apiKey": "super-secret-value"},
                        }
                    ],
                    "connections": {},
                }
            ),
        )
        zf.writestr("repo/malformed.json", "{not-json")
    return stream.getvalue()


async def _target_run(engine, tmp_path: Path) -> tuple[object, WorkerRun]:
    fixture = await build_execution_fixture(
        engine,
        tmp_path,
        mission_slug=f"MISSION-AUTOMATION-MATERIALIZE-{uuid4().hex}",
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
    plan = await ExecutionPlanService(engine).plan(
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
async def test_materialization_quarantines_raw_and_admits_only_safe_descriptors(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        fixture, worker_run = await _target_run(engine, tmp_path)
        archive = _workflow_archive()
        store = LocalScopedObjectStore(
            namespace="automation-corpus",
            root=tmp_path / "objects",
        )

        async def fetch(_uri: str) -> bytes:
            return archive

        snapshot = await AutomationCorpusAcquisitionService(
            engine,
            object_store=store,
            fetch=fetch,
        ).acquire_snapshot(
            worker_run=worker_run,
            commit_sha="c" * 40,
            idempotency_key="materialization-fixture",
        )
        assert snapshot.state == "QUARANTINED"
        assert snapshot.license_state == "VERIFIED"
        assert snapshot.workflow_count == 4

        service = AutomationCorpusMaterializationService(
            engine,
            object_store=store,
        )
        result = await service.materialize_snapshot(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            snapshot_id=snapshot.snapshot_id,
        )
        assert result.processed_workflows == 4
        assert result.sanitized_workflows == 2
        assert result.blocked_workflows == 1
        assert result.rejected_workflows == 1
        assert result.descriptor_count == 2
        assert result.positive_descriptors == 1
        assert result.anti_pattern_descriptors == 1

        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            workflow_states = (
                await uow.connection.execute(
                    text(
                        "SELECT state, count(*) FROM automation_workflow_artifacts "
                        "WHERE snapshot_id=:snapshot GROUP BY state ORDER BY state"
                    ),
                    {"snapshot": snapshot.snapshot_id},
                )
            ).all()
            assert dict(workflow_states) == {
                "BLOCKED": 1,
                "REJECTED": 1,
                "SANITIZED": 2,
            }
            raw_admissions = (
                (
                    await uow.connection.execute(
                        text(
                            "SELECT a.state FROM source_admissions a "
                            "JOIN source_artifacts s ON s.artifact_id=a.artifact_id "
                            "WHERE s.parent_artifact_id=:snapshot_artifact "
                            "AND s.artifact_kind='RAW_AUTOMATION_WORKFLOW'"
                        ),
                        {"snapshot_artifact": snapshot.artifact_id},
                    )
                )
                .scalars()
                .all()
            )
            assert "ADMITTED" not in raw_admissions
            assert sorted(raw_admissions) == [
                "BLOCKED",
                "QUARANTINED",
                "QUARANTINED",
                "REJECTED",
            ]
            descriptor_rows = (
                (
                    await uow.connection.execute(
                        text(
                            "SELECT d.guidance_polarity, d.implementation_guidance, "
                            "d.anti_pattern_notes, d.worker_safe_capsule, "
                            "s.content_object_ref "
                            "FROM automation_pattern_descriptors d "
                            "JOIN source_artifacts s ON s.artifact_id=d.artifact_id "
                            "WHERE d.snapshot_id=:snapshot ORDER BY d.guidance_polarity"
                        ),
                        {"snapshot": snapshot.snapshot_id},
                    )
                )
                .mappings()
                .all()
            )
        assert [row["guidance_polarity"] for row in descriptor_rows] == [
            "ANTI_PATTERN",
            "POSITIVE",
        ]
        anti, positive = descriptor_rows
        assert anti["implementation_guidance"] == []
        assert anti["anti_pattern_notes"]
        assert positive["implementation_guidance"]
        for row in descriptor_rows:
            rendered_capsule = json.dumps(row["worker_safe_capsule"], sort_keys=True)
            assert "nodes" not in rendered_capsule
            assert "connections" not in rendered_capsule
            assert "super-secret-value" not in rendered_capsule
            descriptor_bytes = store.read(
                tenant_id=fixture.tenant.tenant_id,
                project_id=fixture.tenant.project_id,
                key=row["content_object_ref"],
            )
            rendered_descriptor = descriptor_bytes.decode()
            assert "super-secret-value" not in rendered_descriptor
            assert "connections" not in rendered_descriptor
            assert "nodes" not in rendered_descriptor

        second = await service.materialize_snapshot(
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
            snapshot_id=snapshot.snapshot_id,
        )
        assert second == result
        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant.tenant_id,
            project_id=fixture.tenant.project_id,
        ) as uow:
            workflow_count = await uow.connection.execute(
                text(
                    "SELECT count(*) FROM automation_workflow_artifacts "
                    "WHERE snapshot_id=:snapshot"
                ),
                {"snapshot": snapshot.snapshot_id},
            )
            descriptor_count = await uow.connection.execute(
                text(
                    "SELECT count(*) FROM automation_pattern_descriptors "
                    "WHERE snapshot_id=:snapshot"
                ),
                {"snapshot": snapshot.snapshot_id},
            )
            assert workflow_count.scalar_one() == 4
            assert descriptor_count.scalar_one() == 2
    finally:
        await engine.dispose()
