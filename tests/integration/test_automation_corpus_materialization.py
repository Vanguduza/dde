"""PostgreSQL certification for raw quarantine -> sanitized descriptor materialization."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from engine.contracts.automation_corpus_snapshot import AutomationCorpusSnapshot
from engine.contracts.source_artifact import SourceArtifact
from engine.core.ids import uuid7
from engine.object_store.durable import LocalScopedObjectStore
from engine.source.materialization import AutomationCorpusMaterializationService
from engine.source.repository import SourceRepository
from engine.source.service import SourceService
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine, seed_tenant

pytestmark = pytest.mark.integration


def _workflow_archive() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:
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


@pytest.mark.asyncio
async def test_materialization_quarantines_raw_and_admits_only_safe_descriptors(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        source_service = SourceService(engine)
        repository = SourceRepository()
        source = await source_service.ensure_source(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            provider_key="automation:test-corpus",
            display_name="Automation materialization fixture",
            source_domain="AUTOMATION",
            source_class="MAINTAINED_OSS",
            source_kind="PUBLIC_WORKFLOW_CORPUS",
            source_trust="S4_MAINTAINED_OSS",
        )
        archive = _workflow_archive()
        archive_hash = sha256(archive).hexdigest()
        store = LocalScopedObjectStore(
            namespace="automation-corpus",
            root=tmp_path / "objects",
        )
        object_ref = store.put(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            content_hash=archive_hash,
            content=archive,
        )
        now = datetime.now(UTC)
        snapshot_artifact = await source_service.register_artifact(
            SourceArtifact(
                artifact_id=uuid7(),
                source_id=source.source_id,
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                parent_artifact_id=None,
                artifact_kind="AUTOMATION_CORPUS_SNAPSHOT",
                provider_artifact_key="fixture@" + ("c" * 40),
                title="materialization fixture",
                source_uri="https://codeload.github.com/fixture",
                revision="c" * 40,
                content_hash=archive_hash,
                content_object_ref=object_ref,
                content_object_backend="LOCAL",
                content_size_bytes=len(archive),
                media_type="application/zip",
                metadata={},
                provenance={"fixture": True},
                created_at=now,
                updated_at=now,
            )
        )
        snapshot = AutomationCorpusSnapshot(
            snapshot_id=uuid7(),
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            source_id=source.source_id,
            artifact_id=snapshot_artifact.artifact_id,
            repository="Zie619/n8n-workflows",
            commit_sha="c" * 40,
            archive_sha256=archive_hash,
            acquisition_policy_version="test",
            acquisition_policy_hash="d" * 64,
            acquisition_effect_id=uuid7(),
            acquired_at=now,
            compressed_bytes=len(archive),
            expanded_bytes=1,
            workflow_count=4,
            object_ref=object_ref,
            object_backend="LOCAL",
            state="QUARANTINED",
            license_state="VERIFIED",
            license_path="repo/LICENSE",
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
        ) as uow:
            snapshot = await repository.insert_snapshot(uow.connection, snapshot)
            await uow.commit()

        service = AutomationCorpusMaterializationService(
            engine,
            repository=repository,
            source_service=source_service,
            object_store=store,
        )
        result = await service.materialize_snapshot(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
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
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
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
                await uow.connection.execute(
                    text(
                        "SELECT a.state FROM source_admissions a "
                        "JOIN source_artifacts s ON s.artifact_id=a.artifact_id "
                        "WHERE s.parent_artifact_id=:snapshot_artifact "
                        "AND s.artifact_kind='RAW_AUTOMATION_WORKFLOW'"
                    ),
                    {"snapshot_artifact": snapshot.artifact_id},
                )
            ).scalars().all()
            assert "ADMITTED" not in raw_admissions
            assert sorted(raw_admissions) == [
                "BLOCKED",
                "QUARANTINED",
                "QUARANTINED",
                "REJECTED",
            ]
            descriptor_rows = (
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
            ).mappings().all()
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
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                key=row["content_object_ref"],
            )
            rendered_descriptor = descriptor_bytes.decode()
            assert "super-secret-value" not in rendered_descriptor
            assert "connections" not in rendered_descriptor
            assert "nodes" not in rendered_descriptor

        second = await service.materialize_snapshot(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            snapshot_id=snapshot.snapshot_id,
        )
        assert second == result
        async with open_unit_of_work(
            engine,
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
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
