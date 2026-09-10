"""Project-scoped persistence for Production VEKL authorities."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.contracts.stack_fingerprint import StackFingerprint
from engine.contracts.task_signature import TaskSignature
from engine.contracts.vekl_activation_manifest import VEKLActivationManifest
from engine.contracts.vekl_manifest_invalidation import VEKLManifestInvalidation
from engine.contracts.vekl_resource import VEKLResource
from engine.contracts.vekl_resource_outcome import VEKLResourceOutcome
from engine.vekl.tables import (
    stack_fingerprints,
    task_signatures,
    vekl_activation_manifests,
    vekl_manifest_invalidations,
    vekl_resource_outcomes,
    vekl_resources,
)


class VEKLRepository:
    async def insert_resource(
        self, connection: AsyncConnection, resource: VEKLResource
    ) -> None:
        await connection.execute(
            vekl_resources.insert().values(**resource.model_dump())
        )

    async def get_resource(
        self, connection: AsyncConnection, *, project_id: UUID, resource_id: UUID
    ) -> VEKLResource | None:
        result = await connection.execute(
            select(vekl_resources).where(
                vekl_resources.c.project_id == project_id,
                vekl_resources.c.resource_id == resource_id,
            )
        )
        row = result.mappings().first()
        return None if row is None else VEKLResource.model_validate(dict(row))

    async def list_resources(
        self, connection: AsyncConnection, *, project_id: UUID
    ) -> list[VEKLResource]:
        result = await connection.execute(
            select(vekl_resources)
            .where(vekl_resources.c.project_id == project_id)
            .order_by(vekl_resources.c.created_at, vekl_resources.c.resource_id)
        )
        return [VEKLResource.model_validate(dict(row)) for row in result.mappings()]

    async def transition_resource(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        resource_id: UUID,
        lifecycle_state: str,
        updated_at: datetime,
    ) -> None:
        await connection.execute(
            update(vekl_resources)
            .where(
                vekl_resources.c.project_id == project_id,
                vekl_resources.c.resource_id == resource_id,
            )
            .values(lifecycle_state=lifecycle_state, updated_at=updated_at)
        )

    async def insert_fingerprint(
        self, connection: AsyncConnection, record: StackFingerprint
    ) -> None:
        await connection.execute(
            stack_fingerprints.insert().values(**record.model_dump())
        )

    async def get_fingerprint(
        self, connection: AsyncConnection, *, project_id: UUID, fingerprint_id: UUID
    ) -> StackFingerprint | None:
        result = await connection.execute(
            select(stack_fingerprints).where(
                stack_fingerprints.c.project_id == project_id,
                stack_fingerprints.c.fingerprint_id == fingerprint_id,
            )
        )
        row = result.mappings().first()
        return None if row is None else StackFingerprint.model_validate(dict(row))

    async def fingerprint_by_hash(
        self, connection: AsyncConnection, *, project_id: UUID, fingerprint_hash: str
    ) -> StackFingerprint | None:
        result = await connection.execute(
            select(stack_fingerprints).where(
                stack_fingerprints.c.project_id == project_id,
                stack_fingerprints.c.fingerprint_hash == fingerprint_hash,
            )
        )
        row = result.mappings().first()
        return None if row is None else StackFingerprint.model_validate(dict(row))

    async def insert_signature(
        self, connection: AsyncConnection, record: TaskSignature
    ) -> None:
        await connection.execute(task_signatures.insert().values(**record.model_dump()))

    async def get_signature(
        self, connection: AsyncConnection, *, project_id: UUID, signature_id: UUID
    ) -> TaskSignature | None:
        result = await connection.execute(
            select(task_signatures).where(
                task_signatures.c.project_id == project_id,
                task_signatures.c.signature_id == signature_id,
            )
        )
        row = result.mappings().first()
        return None if row is None else TaskSignature.model_validate(dict(row))

    async def signature_by_hash(
        self, connection: AsyncConnection, *, task_id: UUID, signature_hash: str
    ) -> TaskSignature | None:
        result = await connection.execute(
            select(task_signatures).where(
                task_signatures.c.task_id == task_id,
                task_signatures.c.signature_hash == signature_hash,
            )
        )
        row = result.mappings().first()
        return None if row is None else TaskSignature.model_validate(dict(row))

    async def latest_signature_for_task(
        self, connection: AsyncConnection, *, project_id: UUID, task_id: UUID
    ) -> TaskSignature | None:
        result = await connection.execute(
            select(task_signatures)
            .where(
                task_signatures.c.project_id == project_id,
                task_signatures.c.task_id == task_id,
            )
            .order_by(
                task_signatures.c.created_at.desc(),
                task_signatures.c.signature_id.desc(),
            )
            .limit(1)
        )
        row = result.mappings().first()
        return None if row is None else TaskSignature.model_validate(dict(row))

    async def insert_manifest(
        self, connection: AsyncConnection, record: VEKLActivationManifest
    ) -> None:
        await connection.execute(
            vekl_activation_manifests.insert().values(**record.model_dump())
        )

    async def get_manifest(
        self, connection: AsyncConnection, *, project_id: UUID, manifest_id: UUID
    ) -> VEKLActivationManifest | None:
        result = await connection.execute(
            select(vekl_activation_manifests).where(
                vekl_activation_manifests.c.project_id == project_id,
                vekl_activation_manifests.c.manifest_id == manifest_id,
            )
        )
        row = result.mappings().first()
        return None if row is None else VEKLActivationManifest.model_validate(dict(row))

    async def manifest_by_hash(
        self, connection: AsyncConnection, *, project_id: UUID, manifest_hash: str
    ) -> VEKLActivationManifest | None:
        result = await connection.execute(
            select(vekl_activation_manifests).where(
                vekl_activation_manifests.c.project_id == project_id,
                vekl_activation_manifests.c.manifest_hash == manifest_hash,
            )
        )
        row = result.mappings().first()
        return None if row is None else VEKLActivationManifest.model_validate(dict(row))

    async def latest_manifest_for_attempt(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        task_id: UUID,
        task_attempt_id: UUID | None,
    ) -> VEKLActivationManifest | None:
        query = select(vekl_activation_manifests).where(
            vekl_activation_manifests.c.project_id == project_id,
            vekl_activation_manifests.c.task_id == task_id,
        )
        if task_attempt_id is not None:
            query = query.where(
                vekl_activation_manifests.c.task_attempt_id == task_attempt_id
            )
        result = await connection.execute(
            query.order_by(vekl_activation_manifests.c.created_at.desc()).limit(1)
        )
        row = result.mappings().first()
        return None if row is None else VEKLActivationManifest.model_validate(dict(row))

    async def manifests_for_worker_run(
        self,
        connection: AsyncConnection,
        *,
        project_id: UUID,
        worker_run_id: UUID,
    ) -> list[VEKLActivationManifest]:
        result = await connection.execute(
            select(vekl_activation_manifests)
            .where(
                vekl_activation_manifests.c.project_id == project_id,
                vekl_activation_manifests.c.worker_run_id == worker_run_id,
            )
            .order_by(vekl_activation_manifests.c.created_at)
        )
        return [
            VEKLActivationManifest.model_validate(dict(row))
            for row in result.mappings()
        ]

    async def list_manifests(
        self, connection: AsyncConnection, *, project_id: UUID
    ) -> list[VEKLActivationManifest]:
        result = await connection.execute(
            select(vekl_activation_manifests)
            .where(vekl_activation_manifests.c.project_id == project_id)
            .order_by(vekl_activation_manifests.c.created_at.desc())
        )
        return [
            VEKLActivationManifest.model_validate(dict(row))
            for row in result.mappings()
        ]

    async def insert_invalidation(
        self, connection: AsyncConnection, record: VEKLManifestInvalidation
    ) -> None:
        await connection.execute(
            vekl_manifest_invalidations.insert().values(**record.model_dump())
        )

    async def invalidations_for_manifest(
        self, connection: AsyncConnection, *, manifest_id: UUID
    ) -> list[VEKLManifestInvalidation]:
        result = await connection.execute(
            select(vekl_manifest_invalidations)
            .where(vekl_manifest_invalidations.c.manifest_id == manifest_id)
            .order_by(vekl_manifest_invalidations.c.created_at)
        )
        return [
            VEKLManifestInvalidation.model_validate(dict(row))
            for row in result.mappings()
        ]

    async def insert_outcome(
        self, connection: AsyncConnection, record: VEKLResourceOutcome
    ) -> None:
        await connection.execute(
            vekl_resource_outcomes.insert().values(**record.model_dump())
        )

    async def list_outcomes(
        self, connection: AsyncConnection, *, project_id: UUID
    ) -> list[VEKLResourceOutcome]:
        result = await connection.execute(
            select(vekl_resource_outcomes)
            .where(vekl_resource_outcomes.c.project_id == project_id)
            .order_by(vekl_resource_outcomes.c.created_at.desc())
        )
        return [
            VEKLResourceOutcome.model_validate(dict(row)) for row in result.mappings()
        ]
