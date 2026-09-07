"""Anchored design-comment lifecycle for DDE-069."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.design_comment import DesignComment
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.pxg.service import PxgService, validate_key
from engine.studio.tables import design_comments
from engine.truth.db import open_unit_of_work


class DesignCommentService:
    """Sole writer for anchored design review comments."""

    def __init__(self, engine: AsyncEngine, *, pxg: PxgService | None = None) -> None:
        self._engine = engine
        self._pxg = pxg or PxgService(engine)

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        principal_id: UUID,
        pxg_key: str,
        body: str,
        candidate_id: UUID | None = None,
    ) -> DesignComment:
        validate_key(pxg_key)
        if not body.strip():
            raise DdeError("VALIDATION_FAILED", "comment body must not be empty")
        graph = await self._pxg.load(tenant_id=tenant_id, project_id=project_id)
        if graph.node_by_key(pxg_key) is None:
            raise DdeError(
                "ANCHOR_LOST",
                "comment anchor is not present in the current PXG",
                details={"pxg_key": pxg_key},
            )
        now = datetime.now(UTC)
        record = DesignComment(
            comment_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
            pxg_key=pxg_key,
            body=body.strip(),
            status="OPEN",
            created_by=principal_id,
            resolved_by=None,
            resolved_at=None,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                design_comments.insert().values(**record.model_dump())
            )
            await uow.commit()
        return record

    async def resolve(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        principal_id: UUID,
        comment_id: UUID,
    ) -> DesignComment:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                update(design_comments)
                .where(
                    design_comments.c.comment_id == comment_id,
                    design_comments.c.tenant_id == tenant_id,
                    design_comments.c.project_id == project_id,
                    design_comments.c.status == "OPEN",
                )
                .values(
                    status="RESOLVED",
                    resolved_by=principal_id,
                    resolved_at=now,
                    updated_at=now,
                    lock_version=design_comments.c.lock_version + 1,
                )
                .returning(design_comments)
            )
            row = result.mappings().first()
            if row is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "no open comment with that id in this project",
                    details={"comment_id": str(comment_id)},
                )
            await uow.commit()
        return DesignComment.model_validate(dict(row))

    async def list(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID | None = None,
        pxg_key: str | None = None,
        include_resolved: bool = True,
    ) -> tuple[DesignComment, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            query = select(design_comments).where(
                design_comments.c.tenant_id == tenant_id,
                design_comments.c.project_id == project_id,
            )
            if candidate_id is not None:
                query = query.where(design_comments.c.candidate_id == candidate_id)
            if pxg_key is not None:
                query = query.where(design_comments.c.pxg_key == pxg_key)
            if not include_resolved:
                query = query.where(design_comments.c.status == "OPEN")
            result = await uow.connection.execute(
                query.order_by(design_comments.c.created_at.asc())
            )
            return tuple(
                DesignComment.model_validate(dict(row))
                for row in result.mappings().all()
            )
