"""Scoped persistence for DDE-069 M8 Source Intelligence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.design_source import DesignSource
from engine.contracts.design_source_admission import DesignSourceAdmission
from engine.contracts.design_source_artifact import DesignSourceArtifact
from engine.contracts.design_source_search_run import DesignSourceSearchRun
from engine.contracts.frontend_candidate_score import FrontendCandidateScore
from engine.contracts.frontend_provenance_record import FrontendProvenanceRecord
from engine.contracts.frontend_source_blend_preference import (
    FrontendSourceBlendPreference,
)
from engine.contracts.frontend_template import FrontendTemplate
from engine.studio.source.tables import (
    design_source_admissions,
    design_source_artifacts,
    design_source_search_runs,
    design_sources,
    frontend_candidate_scores,
    frontend_provenance_records,
    frontend_source_blend_preferences,
    frontend_templates,
)


def _payload(model: object) -> dict[str, object]:
    data = model.model_dump(mode="python")  # type: ignore[attr-defined]
    for key, value in tuple(data.items()):
        if isinstance(value, UUID):
            continue
        if isinstance(value, tuple):
            data[key] = list(value)
    return cast(dict[str, object], data)


class SourceIntelligenceRepository:
    async def list_sources(
        self, connection: AsyncConnection, *, project_id: UUID
    ) -> tuple[DesignSource, ...]:
        rows = (
            (
                await connection.execute(
                    select(design_sources)
                    .where(design_sources.c.project_id == project_id)
                    .order_by(design_sources.c.priority, design_sources.c.provider_key)
                )
            )
            .mappings()
            .all()
        )
        return tuple(DesignSource.model_validate(dict(row)) for row in rows)

    async def get_source_by_key(
        self, connection: AsyncConnection, *, project_id: UUID, provider_key: str
    ) -> DesignSource | None:
        row = (
            (
                await connection.execute(
                    select(design_sources).where(
                        design_sources.c.project_id == project_id,
                        design_sources.c.provider_key == provider_key,
                    )
                )
            )
            .mappings()
            .first()
        )
        return DesignSource.model_validate(dict(row)) if row else None

    async def upsert_source(
        self, connection: AsyncConnection, record: DesignSource
    ) -> DesignSource:
        existing = await self.get_source_by_key(
            connection, project_id=record.project_id, provider_key=record.provider_key
        )
        if existing is None:
            await connection.execute(design_sources.insert().values(**_payload(record)))
            return record
        values = _payload(record)
        values.pop("source_id", None)
        values["lock_version"] = existing.lock_version + 1
        values["created_at"] = existing.created_at
        row = (
            (
                await connection.execute(
                    update(design_sources)
                    .where(
                        design_sources.c.source_id == existing.source_id,
                        design_sources.c.lock_version == existing.lock_version,
                    )
                    .values(**values)
                    .returning(design_sources)
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise RuntimeError("source registry version changed")
        return DesignSource.model_validate(dict(row))

    async def insert_search(
        self, connection: AsyncConnection, record: DesignSourceSearchRun
    ) -> None:
        await connection.execute(
            design_source_search_runs.insert().values(**_payload(record))
        )

    async def finish_search(
        self,
        connection: AsyncConnection,
        *,
        search_run_id: UUID,
        status: str,
        result_count: int,
        degradation: dict[str, object],
    ) -> DesignSourceSearchRun:
        now = datetime.now(UTC)
        row = (
            (
                await connection.execute(
                    update(design_source_search_runs)
                    .where(design_source_search_runs.c.search_run_id == search_run_id)
                    .values(
                        status=status,
                        result_count=result_count,
                        degradation=degradation,
                        completed_at=now,
                        updated_at=now,
                    )
                    .returning(design_source_search_runs)
                )
            )
            .mappings()
            .one()
        )
        return DesignSourceSearchRun.model_validate(dict(row))

    async def upsert_artifact(
        self, connection: AsyncConnection, record: DesignSourceArtifact
    ) -> DesignSourceArtifact:
        existing = (
            (
                await connection.execute(
                    select(design_source_artifacts).where(
                        design_source_artifacts.c.source_id == record.source_id,
                        design_source_artifacts.c.provider_artifact_key
                        == record.provider_artifact_key,
                    )
                )
            )
            .mappings()
            .first()
        )
        if existing is None:
            await connection.execute(
                design_source_artifacts.insert().values(**_payload(record))
            )
            return record
        existing_model = DesignSourceArtifact.model_validate(dict(existing))
        values = _payload(record)
        values.pop("artifact_id", None)
        values["created_at"] = existing_model.created_at
        row = (
            (
                await connection.execute(
                    update(design_source_artifacts)
                    .where(
                        design_source_artifacts.c.artifact_id
                        == existing_model.artifact_id
                    )
                    .values(**values)
                    .returning(design_source_artifacts)
                )
            )
            .mappings()
            .one()
        )
        return DesignSourceArtifact.model_validate(dict(row))

    async def get_artifact(
        self, connection: AsyncConnection, *, artifact_id: UUID
    ) -> DesignSourceArtifact | None:
        row = (
            (
                await connection.execute(
                    select(design_source_artifacts).where(
                        design_source_artifacts.c.artifact_id == artifact_id
                    )
                )
            )
            .mappings()
            .first()
        )
        return DesignSourceArtifact.model_validate(dict(row)) if row else None

    async def list_artifacts(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        source_id: UUID | None = None,
    ) -> tuple[DesignSourceArtifact, ...]:
        query = select(design_source_artifacts).where(
            design_source_artifacts.c.project_id == project_id
        )
        if source_id is not None:
            query = query.where(design_source_artifacts.c.source_id == source_id)
        rows = (
            (await connection.execute(query.order_by(design_source_artifacts.c.title)))
            .mappings()
            .all()
        )
        return tuple(DesignSourceArtifact.model_validate(dict(row)) for row in rows)

    async def insert_admission(
        self, connection: AsyncConnection, record: DesignSourceAdmission
    ) -> DesignSourceAdmission:
        existing = (
            (
                await connection.execute(
                    select(design_source_admissions).where(
                        design_source_admissions.c.artifact_id == record.artifact_id,
                        design_source_admissions.c.content_hash == record.content_hash,
                        design_source_admissions.c.compiler_version
                        == record.compiler_version,
                    )
                )
            )
            .mappings()
            .first()
        )
        if existing:
            return DesignSourceAdmission.model_validate(dict(existing))
        await connection.execute(
            design_source_admissions.insert().values(**_payload(record))
        )
        return record

    async def latest_admission(
        self, connection: AsyncConnection, *, artifact_id: UUID
    ) -> DesignSourceAdmission | None:
        row = (
            (
                await connection.execute(
                    select(design_source_admissions)
                    .where(design_source_admissions.c.artifact_id == artifact_id)
                    .order_by(design_source_admissions.c.created_at.desc())
                    .limit(1)
                )
            )
            .mappings()
            .first()
        )
        return DesignSourceAdmission.model_validate(dict(row)) if row else None

    async def insert_provenance(
        self, connection: AsyncConnection, record: FrontendProvenanceRecord
    ) -> None:
        await connection.execute(
            frontend_provenance_records.insert().values(**_payload(record))
        )

    async def update_provenance_metadata(
        self,
        connection: AsyncConnection,
        *,
        provenance_id: UUID,
        metadata: dict[str, object],
    ) -> None:
        await connection.execute(
            update(frontend_provenance_records)
            .where(frontend_provenance_records.c.provenance_id == provenance_id)
            .values(metadata=metadata, updated_at=datetime.now(UTC))
        )

    async def provenance_for_subject(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        subject_kind: str,
        subject_ref: str,
    ) -> tuple[FrontendProvenanceRecord, ...]:
        rows = (
            (
                await connection.execute(
                    select(frontend_provenance_records)
                    .where(
                        frontend_provenance_records.c.project_id == project_id,
                        frontend_provenance_records.c.subject_kind == subject_kind,
                        frontend_provenance_records.c.subject_ref == subject_ref,
                    )
                    .order_by(frontend_provenance_records.c.created_at)
                )
            )
            .mappings()
            .all()
        )
        return tuple(FrontendProvenanceRecord.model_validate(dict(row)) for row in rows)

    async def insert_template(
        self, connection: AsyncConnection, record: FrontendTemplate
    ) -> None:
        await connection.execute(frontend_templates.insert().values(**_payload(record)))

    async def list_templates(
        self, connection: AsyncConnection, *, project_id: UUID
    ) -> tuple[FrontendTemplate, ...]:
        rows = (
            (
                await connection.execute(
                    select(frontend_templates)
                    .where(frontend_templates.c.project_id == project_id)
                    .order_by(frontend_templates.c.created_at.desc())
                )
            )
            .mappings()
            .all()
        )
        return tuple(FrontendTemplate.model_validate(dict(row)) for row in rows)

    async def next_score_sequence(
        self, connection: AsyncConnection, *, candidate_id: UUID
    ) -> int:
        value = await connection.scalar(
            select(func.max(frontend_candidate_scores.c.sequence)).where(
                frontend_candidate_scores.c.candidate_id == candidate_id
            )
        )
        return int(value or 0) + 1

    async def insert_score(
        self, connection: AsyncConnection, record: FrontendCandidateScore
    ) -> None:
        await connection.execute(
            frontend_candidate_scores.insert().values(**_payload(record))
        )

    async def latest_score(
        self, connection: AsyncConnection, *, candidate_id: UUID
    ) -> FrontendCandidateScore | None:
        row = (
            (
                await connection.execute(
                    select(frontend_candidate_scores)
                    .where(frontend_candidate_scores.c.candidate_id == candidate_id)
                    .order_by(frontend_candidate_scores.c.sequence.desc())
                    .limit(1)
                )
            )
            .mappings()
            .first()
        )
        return FrontendCandidateScore.model_validate(dict(row)) if row else None

    async def active_source_blend(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        scope_key: str,
    ) -> FrontendSourceBlendPreference | None:
        row = (
            (
                await connection.execute(
                    select(frontend_source_blend_preferences)
                    .where(
                        frontend_source_blend_preferences.c.project_id == project_id,
                        frontend_source_blend_preferences.c.scope_key == scope_key,
                        frontend_source_blend_preferences.c.status == "ACTIVE",
                    )
                    .order_by(frontend_source_blend_preferences.c.created_at.desc())
                    .limit(1)
                )
            )
            .mappings()
            .first()
        )
        return FrontendSourceBlendPreference.model_validate(dict(row)) if row else None

    async def replace_source_blend(
        self,
        connection: AsyncConnection,
        record: FrontendSourceBlendPreference,
    ) -> FrontendSourceBlendPreference:
        prior = await self.active_source_blend(
            connection, project_id=record.project_id, scope_key=record.scope_key
        )
        if prior is not None:
            await connection.execute(
                update(frontend_source_blend_preferences)
                .where(
                    frontend_source_blend_preferences.c.preference_id
                    == prior.preference_id,
                    frontend_source_blend_preferences.c.status == "ACTIVE",
                )
                .values(
                    status="SUPERSEDED",
                    lock_version=prior.lock_version + 1,
                    updated_at=record.created_at,
                )
            )
        await connection.execute(
            frontend_source_blend_preferences.insert().values(**_payload(record))
        )
        return record
