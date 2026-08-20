"""Production Project Truth engine — the sole writer of Truth tables in PostgreSQL
(Chapter 2.4, 3.5, 3.8).

Unlike the in-memory `TruthEngine` test double in `engine.truth.engine`, every
method here requires an explicit tenant/project scope: fail-closed row-level
security (Chapter 3.2) makes scope mandatory context for any read or write, not
an implicit property derivable from a row id alone.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.edr import Edr
from engine.contracts.product_constitution_version import ProductConstitutionVersion
from engine.contracts.requirement import Requirement
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex
from engine.core.ids import uuid7
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.truth.engine import REQUIRED_CONSTITUTION_HEADINGS
from engine.truth.repository import TruthRepository

T = TypeVar("T")


class TruthService:
    """Async, PostgreSQL-backed writer for `product_constitution_versions`,
    `requirements` and `edrs`. Each public method opens and commits its own
    unit of work unless one is supplied, so a future command handler composing
    a cross-module transaction (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: TruthRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or TruthRepository()
        self._clock = clock or SystemClock()

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await body(owned)
            await owned.commit()
            return result

    async def publish_constitution(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        body_markdown: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> ProductConstitutionVersion:
        missing = [
            heading
            for heading in REQUIRED_CONSTITUTION_HEADINGS
            if heading not in body_markdown
        ]
        if missing:
            raise DdeError(
                "POLICY_DENIED",
                "Product Constitution is missing required Chapter 2.4 headings",
                details={"missing": missing},
            )

        async def _op(active: PostgresUnitOfWork) -> ProductConstitutionVersion:
            current = await self._repository.get_active_constitution(
                active.connection, project_id
            )
            now = self._clock.now()
            if current is not None:
                await self._repository.update_constitution_status(
                    active.connection,
                    current.version_id,
                    status="superseded",
                    updated_at=now,
                )
            version = 1 if current is None else current.version + 1
            record = ProductConstitutionVersion(
                version_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                version=version,
                status="active",
                body_markdown=body_markdown,
                content_hash=sha256_hex(body_markdown),
                supersedes_id=None if current is None else current.version_id,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_constitution(active.connection, record)
            return record

        return await self._run(uow, tenant_id, project_id, _op)

    async def draft_requirement(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        slug: str,
        statement: str,
        constraints: list[str],
        acceptance_conditions: list[str],
        supersedes_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> Requirement:
        if not statement.strip():
            raise DdeError("POLICY_DENIED", "Requirement statement must be testable")
        if not acceptance_conditions:
            raise DdeError(
                "POLICY_DENIED", "Requirement must declare acceptance conditions"
            )

        async def _op(active: PostgresUnitOfWork) -> Requirement:
            existing = await self._repository.get_requirement_by_slug(
                active.connection, project_id, slug
            )
            if existing is not None:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Requirement slug is immutable and already used",
                    details={"slug": slug},
                )
            now = self._clock.now()
            record = Requirement(
                requirement_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                slug=slug,
                statement=statement,
                constraints=constraints,
                acceptance_conditions=acceptance_conditions,
                status="draft",
                supersedes_id=supersedes_id,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_requirement(active.connection, record)
            return record

        return await self._run(uow, tenant_id, project_id, _op)

    async def approve_requirement(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        requirement_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> Requirement:
        async def _op(active: PostgresUnitOfWork) -> Requirement:
            record = await self._require_requirement(active, requirement_id)
            if record.status == "approved":
                return record
            if record.status != "draft":
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Only draft requirements can be approved",
                    details={"status": record.status},
                )
            now = self._clock.now()
            await self._repository.update_requirement_status(
                active.connection, requirement_id, status="approved", updated_at=now
            )
            if record.supersedes_id is not None:
                prior = await self._require_requirement(active, record.supersedes_id)
                await self._repository.update_requirement_status(
                    active.connection,
                    prior.requirement_id,
                    status="superseded",
                    updated_at=now,
                )
            return await self._require_requirement(active, requirement_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def retire_requirement(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        requirement_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> Requirement:
        async def _op(active: PostgresUnitOfWork) -> Requirement:
            record = await self._require_requirement(active, requirement_id)
            if record.status == "draft":
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Draft requirements are withdrawn by non-approval, not retired",
                )
            now = self._clock.now()
            await self._repository.update_requirement_status(
                active.connection, requirement_id, status="retired", updated_at=now
            )
            return await self._require_requirement(active, requirement_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def propose_edr(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        slug: str,
        context: str,
        alternatives: list[str],
        decision: str,
        rationale: str,
        consequences: list[str],
        affected_requirement_slugs: list[str],
        supersedes_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> Edr:
        if not alternatives:
            raise DdeError("POLICY_DENIED", "EDR must record alternatives")

        async def _op(active: PostgresUnitOfWork) -> Edr:
            existing = await self._repository.get_edr_by_slug(
                active.connection, project_id, slug
            )
            if existing is not None:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "EDR slug is immutable and already used",
                    details={"slug": slug},
                )
            now = self._clock.now()
            record = Edr(
                edr_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                slug=slug,
                context=context,
                alternatives=alternatives,
                decision=decision,
                rationale=rationale,
                consequences=consequences,
                affected_requirement_slugs=affected_requirement_slugs,
                status="proposed",
                supersedes_id=supersedes_id,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_edr(active.connection, record)
            return record

        return await self._run(uow, tenant_id, project_id, _op)

    async def accept_edr(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        edr_id: UUID,
        decided_by_principal: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> Edr:
        async def _op(active: PostgresUnitOfWork) -> Edr:
            record = await self._require_edr(active, edr_id)
            if record.status == "accepted":
                return record
            if record.status != "proposed":
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Only proposed EDRs can be accepted",
                    details={"status": record.status},
                )
            now = self._clock.now()
            if record.supersedes_id is not None:
                prior = await self._require_edr(active, record.supersedes_id)
                if prior.status != "accepted":
                    raise DdeError(
                        "VERSION_CONFLICT",
                        "An EDR may only supersede an accepted EDR",
                    )
                await self._repository.update_edr_status(
                    active.connection,
                    prior.edr_id,
                    status="superseded",
                    updated_at=now,
                )
            await self._repository.update_edr_status(
                active.connection,
                edr_id,
                status="accepted",
                updated_at=now,
                decided_by_principal=decided_by_principal,
                decided_at=now,
            )
            return await self._require_edr(active, edr_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_edr(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        edr_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> Edr:
        async def _op(active: PostgresUnitOfWork) -> Edr:
            return await self._require_edr(active, edr_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def revise_edr_decision(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        edr_id: UUID,
        decision: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> Edr:
        """Correct a not-yet-decided EDR's decision text.

        Only a `proposed` EDR is mutable. Once accepted, rejected or
        superseded, an EDR is a made decision (Chapter 2.2 rank 4) — it is
        superseded, never rewritten, so revision is refused outright rather
        than silently ignored."""

        async def _op(active: PostgresUnitOfWork) -> Edr:
            record = await self._require_edr(active, edr_id)
            if record.status != "proposed":
                raise DdeError(
                    "POLICY_DENIED",
                    "Only a proposed EDR's decision may be revised; a decided "
                    "EDR is superseded, never rewritten",
                    details={"status": record.status},
                )
            now = self._clock.now()
            await self._repository.update_edr_content(
                active.connection, edr_id, decision=decision, updated_at=now
            )
            return await self._require_edr(active, edr_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def reject_edr(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        edr_id: UUID,
        decided_by_principal: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> Edr:
        async def _op(active: PostgresUnitOfWork) -> Edr:
            record = await self._require_edr(active, edr_id)
            if record.status != "proposed":
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Only proposed EDRs can be rejected",
                    details={"status": record.status},
                )
            now = self._clock.now()
            await self._repository.update_edr_status(
                active.connection,
                edr_id,
                status="rejected",
                updated_at=now,
                decided_by_principal=decided_by_principal,
                decided_at=now,
            )
            return await self._require_edr(active, edr_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def _require_requirement(
        self, active: PostgresUnitOfWork, requirement_id: UUID
    ) -> Requirement:
        record = await self._repository.get_requirement(
            active.connection, requirement_id
        )
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown requirement")
        return record

    async def _require_edr(self, active: PostgresUnitOfWork, edr_id: UUID) -> Edr:
        record = await self._repository.get_edr(active.connection, edr_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown EDR")
        return record
