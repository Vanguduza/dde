"""Governance recording of decisions as EDRs (Chapter 13.3.5).

"A decision, once made, becomes an EDR" — `GovernanceRecords` is that code
path. It never writes `edrs`, `audit_events`, `events`/`outbox` or
`command_idempotency` rows itself: `TruthService` remains the sole writer of
Project Truth (Chapter 3.8), `AuditService` remains the sole writer of the
audit ledger, `EventService` remains the sole writer of the event store and
its outbox companion (Chapter 3.8: "Event ... Owning aggregate transaction
... Outbox"), and `CommandLedger` remains the sole writer of the command
idempotency ledger (Chapter 3.7, 12.5). What this module owns is composing
those calls into one PostgreSQL transaction (Chapter 3.5), so a decision,
its audit trail and its domain event commit — or roll back — together.

This module records EDR accept/reject. Chapter 13.1 `Approval` is a
distinct object owned by `ApprovalService` (DDE-026); a decision may
carry `edr_id` when the caller records it through `TruthService`.
Automatic minting of an EDR on every `ApprovalService.decide` is
deferred — Approval is not itself a Project Truth row.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.audit.service import AuditService
from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.edr import Edr
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.truth.db import open_unit_of_work
from engine.truth.service import TruthService


def _request_hash(*, operation: str, edr_id: UUID, decided_by_principal: UUID) -> str:
    return sha256_hex(
        canonical_json(
            {
                "operation": operation,
                "edr_id": str(edr_id),
                "decided_by_principal": str(decided_by_principal),
            }
        )
    )


class GovernanceRecords:
    """Records governance decisions (accept/reject) as EDRs, auditing each
    decision and appending its domain event in the same unit of work as the
    EDR status change. An optional `idempotency_key` guards the whole
    decision (Chapter 12.5): a repeat with the same key never re-executes
    the EDR mutation, it returns the first call's result instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        truth: TruthService,
        audit: AuditService,
        events: EventService,
        commands: CommandLedger | None = None,
    ) -> None:
        self._engine = engine
        self._truth = truth
        self._audit = audit
        self._events = events
        self._commands = commands or CommandLedger(engine)

    async def accept_decision(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        edr_id: UUID,
        decided_by_principal: UUID,
        idempotency_key: str | None = None,
    ) -> Edr:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            command_id: UUID | None = None
            if idempotency_key is not None:
                request_hash = _request_hash(
                    operation="accept_edr",
                    edr_id=edr_id,
                    decided_by_principal=decided_by_principal,
                )
                record, is_new = await self._commands.begin(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    uow=uow,
                )
                if not is_new:
                    await uow.commit()
                    return self._replay_or_raise(record)
                command_id = record.command_id

            before = await self._truth.get_edr(
                tenant_id=tenant_id, project_id=project_id, edr_id=edr_id, uow=uow
            )
            accepted = await self._truth.accept_edr(
                tenant_id=tenant_id,
                project_id=project_id,
                edr_id=edr_id,
                decided_by_principal=decided_by_principal,
                uow=uow,
            )
            if before.status != "accepted":
                await self._audit.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="edr.accepted",
                    payload={
                        "edr_id": str(accepted.edr_id),
                        "slug": accepted.slug,
                        "decided_by_principal": str(decided_by_principal),
                    },
                    uow=uow,
                )
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="EdrAccepted",
                    aggregate_type="edr",
                    aggregate_id=accepted.edr_id,
                    payload={
                        "edr_id": str(accepted.edr_id),
                        "slug": accepted.slug,
                        "decided_by_principal": str(decided_by_principal),
                    },
                    uow=uow,
                )
                if accepted.supersedes_id is not None:
                    prior = await self._truth.get_edr(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        edr_id=accepted.supersedes_id,
                        uow=uow,
                    )
                    await self._events.append(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        event_type="EdrSuperseded",
                        aggregate_type="edr",
                        aggregate_id=prior.edr_id,
                        payload={
                            "edr_id": str(prior.edr_id),
                            "slug": prior.slug,
                            "superseded_by": str(accepted.edr_id),
                        },
                        uow=uow,
                    )
            if command_id is not None:
                await self._commands.complete(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    command_id=command_id,
                    result=accepted.model_dump(mode="json"),
                    uow=uow,
                )
            await uow.commit()
        return accepted

    async def reject_decision(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        edr_id: UUID,
        decided_by_principal: UUID,
        idempotency_key: str | None = None,
    ) -> Edr:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            command_id: UUID | None = None
            if idempotency_key is not None:
                request_hash = _request_hash(
                    operation="reject_edr",
                    edr_id=edr_id,
                    decided_by_principal=decided_by_principal,
                )
                record, is_new = await self._commands.begin(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    uow=uow,
                )
                if not is_new:
                    await uow.commit()
                    return self._replay_or_raise(record)
                command_id = record.command_id

            before = await self._truth.get_edr(
                tenant_id=tenant_id, project_id=project_id, edr_id=edr_id, uow=uow
            )
            rejected = await self._truth.reject_edr(
                tenant_id=tenant_id,
                project_id=project_id,
                edr_id=edr_id,
                decided_by_principal=decided_by_principal,
                uow=uow,
            )
            if before.status != "rejected":
                await self._audit.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="edr.rejected",
                    payload={
                        "edr_id": str(rejected.edr_id),
                        "slug": rejected.slug,
                        "decided_by_principal": str(decided_by_principal),
                    },
                    uow=uow,
                )
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="EdrRejected",
                    aggregate_type="edr",
                    aggregate_id=rejected.edr_id,
                    payload={
                        "edr_id": str(rejected.edr_id),
                        "slug": rejected.slug,
                        "decided_by_principal": str(decided_by_principal),
                    },
                    uow=uow,
                )
            if command_id is not None:
                await self._commands.complete(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    command_id=command_id,
                    result=rejected.model_dump(mode="json"),
                    uow=uow,
                )
            await uow.commit()
        return rejected

    def _replay_or_raise(self, record: CommandIdempotency) -> Edr:
        if record.status == "completed" and record.result is not None:
            return Edr.model_validate(record.result)
        if record.status == "failed":
            raise DdeError(
                "VERSION_CONFLICT",
                "Command previously failed; refusing to re-execute",
                details={"idempotency_key": record.idempotency_key},
            )
        raise DdeError(
            "VERSION_CONFLICT",
            "Command is already in progress",
            retryable=True,
            details={"idempotency_key": record.idempotency_key},
        )
