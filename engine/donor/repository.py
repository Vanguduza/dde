"""Async repository for Donor Lab tables (Chapter 3.3 / 13.8)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.donor_artifact import DonorArtifact
from engine.contracts.donor_taint import DonorTaint
from engine.contracts.feature_dna import FeatureDNA
from engine.donor.tables import donor_artifacts, donor_taints, feature_dna


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    return value


class DonorRepository:
    async def insert_artifact(
        self, connection: AsyncConnection, record: DonorArtifact
    ) -> None:
        payload = record.model_dump(mode="python")
        payload["provenance"] = _json_safe(payload["provenance"])
        payload["injection_findings"] = list(payload["injection_findings"])
        await connection.execute(donor_artifacts.insert().values(**payload))

    async def update_artifact_feature_dna(
        self,
        connection: AsyncConnection,
        donor_artifact_id: UUID,
        *,
        feature_dna_id: UUID,
        status: str,
        updated_at: object,
    ) -> None:
        await connection.execute(
            update(donor_artifacts)
            .where(donor_artifacts.c.donor_artifact_id == donor_artifact_id)
            .values(
                feature_dna_id=feature_dna_id,
                status=status,
                updated_at=updated_at,
            )
        )

    async def get_artifact(
        self, connection: AsyncConnection, donor_artifact_id: UUID
    ) -> DonorArtifact | None:
        result = await connection.execute(
            select(donor_artifacts).where(
                donor_artifacts.c.donor_artifact_id == donor_artifact_id
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return DonorArtifact.model_validate(dict(row))

    async def find_by_content_hash(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        content_hash: str,
    ) -> DonorArtifact | None:
        result = await connection.execute(
            select(donor_artifacts).where(
                donor_artifacts.c.project_id == project_id,
                donor_artifacts.c.content_hash == content_hash,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return DonorArtifact.model_validate(dict(row))

    async def list_artifacts_for_project(
        self, connection: AsyncConnection, *, project_id: UUID
    ) -> list[DonorArtifact]:
        result = await connection.execute(
            select(donor_artifacts).where(donor_artifacts.c.project_id == project_id)
        )
        return [
            DonorArtifact.model_validate(dict(row)) for row in result.mappings().all()
        ]

    async def insert_feature_dna(
        self, connection: AsyncConnection, record: FeatureDNA
    ) -> None:
        payload = record.model_dump(mode="python")
        payload["body"] = _json_safe(payload["body"])
        payload["donor_sources"] = list(payload["donor_sources"])
        payload["taint_tags"] = list(payload["taint_tags"])
        await connection.execute(feature_dna.insert().values(**payload))

    async def get_feature_dna(
        self, connection: AsyncConnection, feature_dna_id: UUID
    ) -> FeatureDNA | None:
        result = await connection.execute(
            select(feature_dna).where(feature_dna.c.feature_dna_id == feature_dna_id)
        )
        row = result.mappings().first()
        if row is None:
            return None
        return FeatureDNA.model_validate(dict(row))

    async def find_feature_dna_by_hash(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        dna_hash: str,
    ) -> FeatureDNA | None:
        result = await connection.execute(
            select(feature_dna).where(
                feature_dna.c.project_id == project_id,
                feature_dna.c.dna_hash == dna_hash,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return FeatureDNA.model_validate(dict(row))

    async def insert_taint(
        self, connection: AsyncConnection, record: DonorTaint
    ) -> None:
        payload = record.model_dump(mode="python")
        payload["taint_tags"] = list(payload["taint_tags"])
        await connection.execute(donor_taints.insert().values(**payload))

    async def find_taint(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        subject_kind: str,
        subject_id: UUID,
        donor_artifact_id: UUID,
    ) -> DonorTaint | None:
        result = await connection.execute(
            select(donor_taints).where(
                donor_taints.c.project_id == project_id,
                donor_taints.c.subject_kind == subject_kind,
                donor_taints.c.subject_id == subject_id,
                donor_taints.c.donor_artifact_id == donor_artifact_id,
            )
        )
        row = result.mappings().first()
        if row is None:
            return None
        return DonorTaint.model_validate(dict(row))

    async def list_taints_for_subject(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        subject_kind: str,
        subject_id: UUID,
    ) -> list[DonorTaint]:
        result = await connection.execute(
            select(donor_taints).where(
                donor_taints.c.project_id == project_id,
                donor_taints.c.subject_kind == subject_kind,
                donor_taints.c.subject_id == subject_id,
            )
        )
        return [DonorTaint.model_validate(dict(row)) for row in result.mappings().all()]
