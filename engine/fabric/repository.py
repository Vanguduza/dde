"""Small scoped PostgreSQL repository helpers for Fabric services."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Table, and_, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql.elements import ColumnElement

from engine.core.errors import DdeError
from engine.truth.db import open_unit_of_work

ModelT = TypeVar("ModelT", bound=BaseModel)


class FabricRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def insert_model(
        self,
        *,
        table: Table,
        model: type[ModelT],
        tenant_id: UUID,
        project_id: UUID,
        values: Mapping[str, object],
    ) -> ModelT:
        async with open_unit_of_work(
            self.engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                insert(table).values(**dict(values)).returning(table)
            )
            row = result.mappings().one()
            await uow.commit()
        return model.model_validate(dict(row))

    async def get_model(
        self,
        *,
        table: Table,
        model: type[ModelT],
        id_column: str,
        object_id: UUID,
        tenant_id: UUID,
        project_id: UUID,
    ) -> ModelT:
        async with open_unit_of_work(
            self.engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(table).where(getattr(table.c, id_column) == object_id)
            )
            row = result.mappings().one_or_none()
        if row is None:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                f"{table.name} row not found in project scope",
                retryable=False,
                details={id_column: str(object_id)},
            )
        return model.model_validate(dict(row))

    async def list_models(
        self,
        *,
        table: Table,
        model: type[ModelT],
        tenant_id: UUID,
        project_id: UUID,
        filters: Mapping[str, object] | None = None,
        order_by: Sequence[ColumnElement[object]] = (),
        limit: int = 200,
    ) -> tuple[ModelT, ...]:
        clauses = []
        for key, value in (filters or {}).items():
            column = getattr(table.c, key)
            clauses.append(column.is_(None) if value is None else column == value)
        stmt = select(table)
        if clauses:
            stmt = stmt.where(and_(*clauses))
        if order_by:
            stmt = stmt.order_by(*order_by)
        stmt = stmt.limit(limit)
        async with open_unit_of_work(
            self.engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(stmt)
            rows = result.mappings().all()
        return tuple(model.model_validate(dict(row)) for row in rows)

    async def update_locked(
        self,
        *,
        table: Table,
        model: type[ModelT],
        id_column: str,
        object_id: UUID,
        tenant_id: UUID,
        project_id: UUID,
        lock_version: int,
        values: Mapping[str, object],
    ) -> ModelT:
        payload = dict(values)
        payload["lock_version"] = lock_version + 1
        async with open_unit_of_work(
            self.engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                update(table)
                .where(
                    getattr(table.c, id_column) == object_id,
                    table.c.lock_version == lock_version,
                )
                .values(**payload)
                .returning(table)
            )
            row = result.mappings().one_or_none()
            if row is None:
                raise DdeError(
                    "VERSION_CONFLICT",
                    f"stale {table.name} update",
                    retryable=True,
                    details={id_column: str(object_id), "lock_version": lock_version},
                )
            await uow.commit()
        return model.model_validate(dict(row))
