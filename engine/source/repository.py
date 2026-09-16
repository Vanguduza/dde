"""Scoped persistence for domain-neutral Source Intelligence and automation corpus."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.automation_corpus_snapshot import AutomationCorpusSnapshot
from engine.contracts.automation_pattern_descriptor import AutomationPatternDescriptor
from engine.contracts.automation_workflow_artifact import AutomationWorkflowArtifact
from engine.contracts.source_admission import SourceAdmission
from engine.contracts.source_artifact import SourceArtifact
from engine.contracts.source_record import SourceRecord
from engine.source.tables import (
    automation_corpus_snapshots,
    automation_pattern_descriptors,
    automation_workflow_artifacts,
    source_admissions,
    source_artifacts,
    source_records,
)


def _payload(model: object) -> dict[str, object]:
    data = model.model_dump(mode="python")  # type: ignore[attr-defined]
    for key, value in tuple(data.items()):
        if isinstance(value, tuple):
            data[key] = list(value)
    return cast(dict[str, object], data)


class SourceRepository:
    async def get_source(
        self, connection: AsyncConnection, *, source_id: UUID
    ) -> SourceRecord | None:
        row = (
            (
                await connection.execute(
                    select(source_records).where(source_records.c.source_id == source_id)
                )
            )
            .mappings()
            .first()
        )
        return SourceRecord.model_validate(dict(row)) if row else None

    async def get_source_by_key(
        self, connection: AsyncConnection, *, project_id: UUID, provider_key: str
    ) -> SourceRecord | None:
        row = (
            (
                await connection.execute(
                    select(source_records).where(
                        source_records.c.project_id == project_id,
                        source_records.c.provider_key == provider_key,
                    )
                )
            )
            .mappings()
            .first()
        )
        return SourceRecord.model_validate(dict(row)) if row else None

    async def upsert_source(
        self, connection: AsyncConnection, record: SourceRecord
    ) -> SourceRecord:
        existing = await self.get_source_by_key(
            connection, project_id=record.project_id, provider_key=record.provider_key
        )
        if existing is None:
            await connection.execute(source_records.insert().values(**_payload(record)))
            return record
        values = _payload(record)
        values.pop("source_id", None)
        values["created_at"] = existing.created_at
        row = (
            (
                await connection.execute(
                    update(source_records)
                    .where(source_records.c.source_id == existing.source_id)
                    .values(**values)
                    .returning(source_records)
                )
            )
            .mappings()
            .one()
        )
        return SourceRecord.model_validate(dict(row))

    async def get_artifact(
        self, connection: AsyncConnection, *, artifact_id: UUID
    ) -> SourceArtifact | None:
        row = (
            (
                await connection.execute(
                    select(source_artifacts).where(source_artifacts.c.artifact_id == artifact_id)
                )
            )
            .mappings()
            .first()
        )
        return SourceArtifact.model_validate(dict(row)) if row else None

    async def insert_artifact(
        self, connection: AsyncConnection, record: SourceArtifact
    ) -> SourceArtifact:
        existing = (
            (
                await connection.execute(
                    select(source_artifacts).where(
                        source_artifacts.c.source_id == record.source_id,
                        source_artifacts.c.provider_artifact_key
                        == record.provider_artifact_key,
                        source_artifacts.c.revision == record.revision,
                        source_artifacts.c.content_hash == record.content_hash,
                    )
                )
            )
            .mappings()
            .first()
        )
        if existing:
            return SourceArtifact.model_validate(dict(existing))
        await connection.execute(source_artifacts.insert().values(**_payload(record)))
        return record

    async def latest_admission(
        self, connection: AsyncConnection, *, artifact_id: UUID
    ) -> SourceAdmission | None:
        row = (
            (
                await connection.execute(
                    select(source_admissions)
                    .where(source_admissions.c.artifact_id == artifact_id)
                    .order_by(source_admissions.c.created_at.desc())
                    .limit(1)
                )
            )
            .mappings()
            .first()
        )
        return SourceAdmission.model_validate(dict(row)) if row else None

    async def insert_admission(
        self, connection: AsyncConnection, record: SourceAdmission
    ) -> SourceAdmission:
        existing = (
            (
                await connection.execute(
                    select(source_admissions).where(
                        source_admissions.c.artifact_id == record.artifact_id,
                        source_admissions.c.content_hash == record.content_hash,
                        source_admissions.c.compiler_version == record.compiler_version,
                        source_admissions.c.policy_version == record.policy_version,
                    )
                )
            )
            .mappings()
            .first()
        )
        if existing:
            return SourceAdmission.model_validate(dict(existing))
        await connection.execute(source_admissions.insert().values(**_payload(record)))
        return record

    async def insert_snapshot(
        self, connection: AsyncConnection, record: AutomationCorpusSnapshot
    ) -> AutomationCorpusSnapshot:
        existing = (
            (
                await connection.execute(
                    select(automation_corpus_snapshots).where(
                        automation_corpus_snapshots.c.project_id == record.project_id,
                        automation_corpus_snapshots.c.repository == record.repository,
                        automation_corpus_snapshots.c.commit_sha == record.commit_sha,
                        automation_corpus_snapshots.c.archive_sha256 == record.archive_sha256,
                    )
                )
            )
            .mappings()
            .first()
        )
        if existing:
            return AutomationCorpusSnapshot.model_validate(dict(existing))
        await connection.execute(
            automation_corpus_snapshots.insert().values(**_payload(record))
        )
        return record

    async def get_snapshot(
        self, connection: AsyncConnection, *, snapshot_id: UUID
    ) -> AutomationCorpusSnapshot | None:
        row = (
            (
                await connection.execute(
                    select(automation_corpus_snapshots).where(
                        automation_corpus_snapshots.c.snapshot_id == snapshot_id
                    )
                )
            )
            .mappings()
            .first()
        )
        return AutomationCorpusSnapshot.model_validate(dict(row)) if row else None

    async def insert_workflow(
        self, connection: AsyncConnection, record: AutomationWorkflowArtifact
    ) -> AutomationWorkflowArtifact:
        existing = (
            (
                await connection.execute(
                    select(automation_workflow_artifacts).where(
                        automation_workflow_artifacts.c.snapshot_id == record.snapshot_id,
                        automation_workflow_artifacts.c.path == record.path,
                        automation_workflow_artifacts.c.raw_hash == record.raw_hash,
                    )
                )
            )
            .mappings()
            .first()
        )
        if existing:
            return AutomationWorkflowArtifact.model_validate(dict(existing))
        await connection.execute(
            automation_workflow_artifacts.insert().values(**_payload(record))
        )
        return record

    async def insert_descriptor(
        self, connection: AsyncConnection, record: AutomationPatternDescriptor
    ) -> AutomationPatternDescriptor:
        existing = (
            (
                await connection.execute(
                    select(automation_pattern_descriptors).where(
                        automation_pattern_descriptors.c.project_id == record.project_id,
                        automation_pattern_descriptors.c.descriptor_hash
                        == record.descriptor_hash,
                    )
                )
            )
            .mappings()
            .first()
        )
        if existing:
            return AutomationPatternDescriptor.model_validate(dict(existing))
        await connection.execute(
            automation_pattern_descriptors.insert().values(**_payload(record))
        )
        return record

    async def descriptors_for_snapshot(
        self, connection: AsyncConnection, *, snapshot_id: UUID
    ) -> tuple[AutomationPatternDescriptor, ...]:
        rows = (
            (
                await connection.execute(
                    select(automation_pattern_descriptors)
                    .where(automation_pattern_descriptors.c.snapshot_id == snapshot_id)
                    .order_by(
                        automation_pattern_descriptors.c.pattern_lineage_id,
                        automation_pattern_descriptors.c.pattern_revision_hash,
                    )
                )
            )
            .mappings()
            .all()
        )
        return tuple(AutomationPatternDescriptor.model_validate(dict(row)) for row in rows)
