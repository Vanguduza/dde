"""DDE-069 Frontend Contract service.

The contract states what a project's frontend is obliged to contain,
independent of what it currently renders. Together with the Project
Experience Graph -- which states what exists -- it lets DDE distinguish
"rendered" from "complete according to product intent".

Versioning is publish-and-supersede rather than edit-in-place: a change
writes a new `contract_version` and demotes the previous ACTIVE row to
SUPERSEDED in the same transaction, so a coverage snapshot can always be
replayed against the exact contract it cited.

Applicability is the no-silent-omission rule
(FRONTEND_STUDIO_REV3 section 13.1). An obligation that is anything other
than REQUIRED or OPTIONAL_SELECTED must name the decision that made it so;
this service refuses the write otherwise, which is what stops "we dropped
it" from being indistinguishable from "we never listed it".

This service is the sole writer of `frontend_contracts`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.contracts.frontend_contract import FrontendContract, Obligation
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.pxg.service import validate_key
from engine.studio.tables import frontend_contracts
from engine.truth.db import open_unit_of_work

#: Applicabilities that remove an obligation from the required set. Each
#: must cite the decision that authorised it -- an unexplained waiver is
#: exactly the silent omission the contract exists to prevent.
WAIVED_APPLICABILITIES: Final[frozenset[str]] = frozenset(
    {"DEFERRED_APPROVED", "NOT_APPLICABLE_APPROVED", "BLOCKED_RECORDED"}
)

COUNTED_APPLICABILITIES: Final[frozenset[str]] = frozenset(
    {"REQUIRED", "OPTIONAL_SELECTED"}
)


def obligation_content_hash(obligations: Sequence[Obligation]) -> str:
    """Stable hash over the obligation set only.

    Excludes ids and timestamps so republishing an identical contract is
    recognisably identical rather than merely similar.
    """
    payload = sorted(
        (
            {
                "dimension": item.dimension,
                "pxg_key": item.pxg_key,
                "statement": item.statement,
                "requirement_refs": sorted(item.requirement_refs),
                "applicability": item.applicability,
                "applicability_decision_ref": item.applicability_decision_ref,
                "verification_kinds": sorted(item.verification_kinds),
            }
            for item in obligations
        ),
        key=lambda entry: (entry["dimension"], entry["pxg_key"]),
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_obligations(obligations: Sequence[Obligation]) -> None:
    if not obligations:
        raise DdeError(
            "VALIDATION_FAILED",
            "a frontend contract with no obligations asserts nothing and "
            "would make every coverage result vacuously complete",
            retryable=False,
        )
    seen: set[tuple[str, str]] = set()
    for item in obligations:
        validate_key(item.pxg_key)
        identity = (item.dimension, item.pxg_key)
        if identity in seen:
            raise DdeError(
                "VALIDATION_FAILED",
                "duplicate obligation for the same dimension and pxg_key",
                retryable=False,
                details={"dimension": item.dimension, "pxg_key": item.pxg_key},
            )
        seen.add(identity)
        if not item.statement.strip():
            raise DdeError(
                "VALIDATION_FAILED",
                "every obligation must carry a statement",
                retryable=False,
                details={"pxg_key": item.pxg_key},
            )
        if (
            item.applicability in WAIVED_APPLICABILITIES
            and not (item.applicability_decision_ref or "").strip()
        ):
            raise DdeError(
                "POLICY_DENIED",
                "a non-required obligation must cite the decision that "
                "waived, deferred or blocked it; silent omission is not a "
                "permitted state",
                retryable=False,
                details={
                    "pxg_key": item.pxg_key,
                    "applicability": item.applicability,
                },
            )


class FrontendContractService:
    """Publishes and reads versioned frontend contracts."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def get_active(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> FrontendContract | None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            return await self._get_active(
                uow.connection, tenant_id=tenant_id, project_id=project_id
            )

    async def _get_active(
        self, connection: AsyncConnection, *, tenant_id: UUID, project_id: UUID
    ) -> FrontendContract | None:
        result = await connection.execute(
            select(frontend_contracts)
            .where(
                frontend_contracts.c.tenant_id == tenant_id,
                frontend_contracts.c.project_id == project_id,
                frontend_contracts.c.status == "ACTIVE",
            )
            .order_by(frontend_contracts.c.contract_version.desc())
            .limit(1)
        )
        row = result.mappings().first()
        return FrontendContract.model_validate(dict(row)) if row else None

    async def get_version(
        self, *, tenant_id: UUID, project_id: UUID, contract_version: int
    ) -> FrontendContract | None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_contracts).where(
                    frontend_contracts.c.tenant_id == tenant_id,
                    frontend_contracts.c.project_id == project_id,
                    frontend_contracts.c.contract_version == contract_version,
                )
            )
            row = result.mappings().first()
        return FrontendContract.model_validate(dict(row)) if row else None

    async def publish(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        obligations: Sequence[Obligation],
        mission_id: UUID | None = None,
    ) -> FrontendContract:
        """Publish a new ACTIVE contract version, superseding the previous.

        Republishing an identical obligation set is a no-op that returns
        the existing ACTIVE row, so a reconciliation loop cannot inflate
        the version number without a real change.
        """
        validate_obligations(obligations)
        content_hash = obligation_content_hash(obligations)
        now = datetime.now(UTC)

        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            connection = uow.connection
            current = await self._get_active(
                connection, tenant_id=tenant_id, project_id=project_id
            )
            if current is not None and current.content_hash == content_hash:
                return current

            next_version = 1 if current is None else current.contract_version + 1
            if current is not None:
                await connection.execute(
                    update(frontend_contracts)
                    .where(
                        frontend_contracts.c.contract_id == current.contract_id,
                        frontend_contracts.c.status == "ACTIVE",
                    )
                    .values(status="SUPERSEDED", updated_at=now)
                )
            record = FrontendContract(
                contract_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                contract_version=next_version,
                content_hash=content_hash,
                status="ACTIVE",
                obligations=list(obligations),
                created_at=now,
                updated_at=now,
            )
            await connection.execute(
                frontend_contracts.insert().values(
                    **record.model_dump(exclude={"obligations"}),
                    # mode="json" so UUID obligation ids serialise into
                    # jsonb rather than failing the driver's encoder.
                    obligations=[item.model_dump(mode="json") for item in obligations],
                )
            )
            await uow.commit()
        return record
