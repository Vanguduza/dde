"""Production Credential Broker (Chapter 14.3) -- the sole writer of
`credential_handles` rows in PostgreSQL (Chapter 3.5, 3.8) and, together with
`engine.capabilities.broker.provider`, the only code in this codebase that
ever holds a raw secret value in memory (AGENTS.md: "Nothing except
`engine/capabilities/broker/**` reads secret material").

**Scope determination (mission DDE-019).** Chapter 14.3 names five broker
operations (`issue`, `renew`, `revoke`, `inspect`, `emergency_revoke`) and a
provider preference order ending in "static secret behind the broker" --
it does not mandate a live external identity federation for the broker to
be real. This codebase has no capability that needs an external credential
today: DDE-016's seeded Stage 1 portfolio (`capability.run_local_process`,
`capability.workspace_filesystem`, `capability.git_operations` --
`engine.capabilities.seed.SEED_CAPABILITIES`) is entirely local-subprocess
and local-git, and no chartered S2/S3 mission introduces a real external
provider either. This mission therefore builds the broker's full, real
mechanics against `engine.capabilities.broker.provider.LocalSecretProvider`
-- a genuine, working instance of the chapter's own lowest preference tier,
clearly labelled as local/synthetic rather than misrepresented as a real
cloud integration. Real external provider integration is deferred to
whichever future mission actually charters a capability that needs one.

**Secret-material persistence design.** A `CredentialHandle` row never
carries the raw secret value -- only `secret_hash`, a SHA-256 digest
(Chapter 14.3: "Audit records store metadata and hashes, never secret
material"). The raw value produced by `issue()`/`renew()` exists only as a
Python string for the duration of that one call and is returned to the
caller exactly once; nothing in this module logs it, includes it in an
event payload, or passes it to `engine.events.idempotency.CommandLedger`'s
`result` column. One direct consequence, stated plainly: a replayed
`issue()`/`renew()` call (the same `idempotency_key` presented twice) can
only return the already-issued handle's metadata, never the original
secret a second time -- there is nothing durable to return it from. A
caller that loses a freshly issued secret before consuming it must
`revoke()` the handle and issue a new one; this is the correct, secure
behaviour for a one-time secret, not a gap.

**What this module does NOT do** -- deferred, not stubbed:
  - Wiring a real caller (`engine.workers`/`engine.workspaces`) to actually
    request a credential before performing a side effect. None of Stage 1's
    three seeded capabilities need one (see above) -- there is no real call
    site to wire yet, and inventing one would violate this mission's own
    constraint against widening any Stage 1/2 module beyond read-only calls.
  - `emergency_revoke`'s "terminates dependent runs" half -- see that
    method's own docstring: there is no run anywhere in this codebase that
    depends on a brokered credential, so there is nothing real to
    terminate.
  - `engine.recovery`'s `ExternalEffect` journal / idempotency ledger
    (DDE-020) -- issuance idempotency reuses the already-built
    `CommandLedger` instead of inventing a second mechanism.
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.broker.hashing import (
    issuance_request_hash,
    renewal_request_hash,
)
from engine.capabilities.broker.provider import (
    CredentialProvider,
    CredentialScope,
    LocalSecretProvider,
)
from engine.capabilities.broker.repository import CredentialHandleRepository
from engine.capabilities.broker.states import (
    CREDENTIAL_HANDLE_TRANSITIONS,
    LIVE_HANDLE_STATUSES,
)
from engine.capabilities.lease_repository import CapabilityLeaseRepository
from engine.contracts.capability_lease import CapabilityLease
from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.credential_handle import CredentialHandle
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

#: Chapter 14.3: "short-lived" -- no chapter names a literal duration
#: (unlike `command_idempotency`'s explicit 30-day rule, Chapter 3.7). This
#: mission's own flagged interpretation, deliberately much shorter than
#: `engine.capabilities.lease_service.DEFAULT_LEASE_TTL` (24h): a brokered
#: credential is meant to live for the span of one operation, not a run.
DEFAULT_CREDENTIAL_TTL = timedelta(minutes=15)


@dataclass(frozen=True)
class IssuedCredential:
    """`handle` is the durable, secret-free record. `secret_value` is the
    real, raw, one-time value -- present on a fresh mint, `None` on an
    idempotent replay (see module docstring)."""

    handle: CredentialHandle
    secret_value: str | None


class CredentialBrokerService:
    """Async, PostgreSQL-backed writer for `credential_handles` (Chapter
    3.8: "Status only" -- a handle's scope fields never change after
    creation; `renew()` mints a new row rather than mutating one). Each
    public method opens and commits its own unit of work unless one is
    supplied, so a caller composing a cross-module transaction (Chapter
    3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: CredentialHandleRepository | None = None,
        lease_repository: CapabilityLeaseRepository | None = None,
        events: EventService | None = None,
        commands: CommandLedger | None = None,
        clock: Clock | None = None,
        provider: CredentialProvider | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or CredentialHandleRepository()
        self._lease_repository = lease_repository or CapabilityLeaseRepository()
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
        self._clock = clock or SystemClock()
        self._provider: CredentialProvider = provider or LocalSecretProvider()

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

    async def issue(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        lease_id: UUID,
        requested_by: str,
        idempotency_key: str,
        ttl: timedelta = DEFAULT_CREDENTIAL_TTL,
        uow: PostgresUnitOfWork | None = None,
    ) -> IssuedCredential:
        """Chapter 14.3's `issue(lease)`: "Only after policy and lease
        validation; returns a short-lived credential or handle bound to
        tenant, project, mission, task, run, capability, resource scope,
        policy version and expiry." `lease_id` is always re-fetched and
        re-validated live (never trusting a caller-supplied snapshot),
        mirroring `engine.capabilities.lease_service.
        CapabilityLeaseService.require_active`'s own fail-closed pattern.
        Only a lease whose live `status` is literally `ACTIVE` (already in
        use, Chapter 9.2) and not expired is granted a credential -- a
        merely `GRANTED`-but-never-activated lease is denied, exactly like
        every other non-`ACTIVE` status."""

        async def _op(active: PostgresUnitOfWork) -> IssuedCredential:
            lease = await self._require_active_lease(active, lease_id)

            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=issuance_request_hash(
                    lease_id=lease_id, requested_by=requested_by
                ),
                uow=active,
            )
            if not is_new:
                return self._replay_or_raise(record)

            now = self._clock.now()
            expires_at = min(now + ttl, lease.expires_at)
            issued = self._provider.issue(_scope_for(lease))
            handle = CredentialHandle(
                handle_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=lease.mission_id,
                task_id=lease.task_id,
                worker_run_id=lease.worker_run_id,
                lease_id=lease.lease_id,
                capability_id=lease.capability_id,
                provider_id=self._provider.provider_id,
                provider_ref=issued.provider_ref,
                resource_scope=dict(lease.resource_scope),
                issued_by_policy_version=lease.issued_by_policy_version,
                secret_hash=sha256_hex(issued.secret_value),
                status="ISSUED",
                issued_at=now,
                expires_at=expires_at,
                revoked_at=None,
                revocation_reason=None,
                supersedes_handle_id=None,
                superseded_by_handle_id=None,
                requested_by=requested_by,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_handle(active.connection, handle)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="CredentialIssued",
                aggregate_type="credential_handle",
                aggregate_id=handle.handle_id,
                mission_id=lease.mission_id,
                task_id=lease.task_id,
                payload={
                    "lease_id": str(lease.lease_id),
                    "capability_id": lease.capability_id,
                    "provider_id": handle.provider_id,
                    "expires_at": handle.expires_at.isoformat(),
                },
                uow=active,
            )
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=handle.model_dump(mode="json"),
                uow=active,
            )
            return IssuedCredential(handle=handle, secret_value=issued.secret_value)

        return await self._run(uow, tenant_id, project_id, _op)

    async def renew(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        handle_id: UUID,
        requested_by: str,
        idempotency_key: str,
        ttl: timedelta = DEFAULT_CREDENTIAL_TTL,
        uow: PostgresUnitOfWork | None = None,
    ) -> IssuedCredential:
        """Chapter 14.3's `renew(lease, credential)`: "Revalidates the
        active lease; issues a replacement; never silently widens
        authority or extends beyond the lease." The replacement is a NEW
        `CredentialHandle` row (`supersedes_handle_id` linked, mirroring
        `CapabilityDescriptor`'s own supersession pattern) -- this method
        never mutates the superseded row's own scope fields. The
        superseded handle's provider-side material is invalidated
        immediately (a conservative reading of "replacement": no overlap
        window), and the row itself moves `ISSUED -> SUPERSEDED`."""

        async def _op(active: PostgresUnitOfWork) -> IssuedCredential:
            current = await self._require_handle(active, handle_id)
            if current.status != "ISSUED":
                raise DdeError(
                    "POLICY_DENIED",
                    f"Credential handle is {current.status}, not live -- fail closed",
                    details={"handle_id": str(handle_id), "status": current.status},
                )
            lease = await self._require_active_lease(active, current.lease_id)

            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=renewal_request_hash(
                    handle_id=handle_id, requested_by=requested_by
                ),
                uow=active,
            )
            if not is_new:
                return self._replay_or_raise(record)

            now = self._clock.now()
            expires_at = min(now + ttl, lease.expires_at)
            issued = self._provider.issue(_scope_for(lease))
            replacement = CredentialHandle(
                handle_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=lease.mission_id,
                task_id=lease.task_id,
                worker_run_id=lease.worker_run_id,
                lease_id=lease.lease_id,
                capability_id=lease.capability_id,
                provider_id=self._provider.provider_id,
                provider_ref=issued.provider_ref,
                resource_scope=dict(lease.resource_scope),
                issued_by_policy_version=lease.issued_by_policy_version,
                secret_hash=sha256_hex(issued.secret_value),
                status="ISSUED",
                issued_at=now,
                expires_at=expires_at,
                revoked_at=None,
                revocation_reason=None,
                supersedes_handle_id=current.handle_id,
                superseded_by_handle_id=None,
                requested_by=requested_by,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_handle(active.connection, replacement)

            self._provider.revoke(current.provider_ref)
            next_status = transition(
                current.status, "SUPERSEDED", CREDENTIAL_HANDLE_TRANSITIONS
            )
            rowcount = await self._repository.update_fields(
                active.connection,
                current.handle_id,
                fields={
                    "status": next_status,
                    "superseded_by_handle_id": replacement.handle_id,
                    "updated_at": now,
                },
            )
            if rowcount != 1:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Unknown credential handle",
                    details={"handle_id": str(current.handle_id)},
                )

            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="CredentialRenewed",
                aggregate_type="credential_handle",
                aggregate_id=replacement.handle_id,
                mission_id=lease.mission_id,
                task_id=lease.task_id,
                payload={
                    "lease_id": str(lease.lease_id),
                    "supersedes_handle_id": str(current.handle_id),
                    "expires_at": replacement.expires_at.isoformat(),
                },
                uow=active,
            )
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=replacement.model_dump(mode="json"),
                uow=active,
            )
            return IssuedCredential(
                handle=replacement, secret_value=issued.secret_value
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def revoke(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        handle_id: UUID,
        reason: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> CredentialHandle:
        """Chapter 14.3's `revoke(credential)`: "Invalidates or quarantines
        at the provider where semantics permit; always invalidates
        locally." Provider-side revocation is attempted first (best
        effort -- `LocalSecretProvider.revoke` is a documented no-op, see
        that module), then the local row is durably transitioned to
        `REVOKED` regardless -- the local invalidation this mission
        actually proves end-to-end."""

        async def _op(active: PostgresUnitOfWork) -> CredentialHandle:
            current = await self._require_handle(active, handle_id)
            self._provider.revoke(current.provider_ref)
            next_status = transition(
                current.status, "REVOKED", CREDENTIAL_HANDLE_TRANSITIONS
            )
            now = self._clock.now()
            rowcount = await self._repository.update_fields(
                active.connection,
                current.handle_id,
                fields={
                    "status": next_status,
                    "revoked_at": now,
                    "revocation_reason": reason,
                    "updated_at": now,
                },
            )
            if rowcount != 1:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Unknown credential handle",
                    details={"handle_id": str(current.handle_id)},
                )
            updated = await self._require_handle(active, current.handle_id)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="CredentialRevoked",
                aggregate_type="credential_handle",
                aggregate_id=updated.handle_id,
                mission_id=updated.mission_id,
                task_id=updated.task_id,
                payload={"reason": reason},
                uow=active,
            )
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def emergency_revoke(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        reason: str,
        mission_id: UUID | None = None,
        worker_run_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[CredentialHandle]:
        """Chapter 14.3's `emergency_revoke(scope)`: "Revokes all active
        material under a tenant/project/mission/run scope, and terminates
        dependent runs." This mission implements the first half in full:
        every still-`ISSUED` handle in the given scope is revoked in one
        transaction via the same mechanics as `revoke()`. "Terminates
        dependent runs" is deliberately NOT implemented -- see this
        module's own docstring: no capability in this codebase requests a
        credential yet, so no run depends on one, so there is nothing real
        to terminate. Wiring that half is deferred to whichever future
        mission actually creates a real credential-consuming call site."""

        async def _op(active: PostgresUnitOfWork) -> list[CredentialHandle]:
            candidates = await self._repository.list_live_in_scope(
                active.connection,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                worker_run_id=worker_run_id,
            )
            now = self._clock.now()
            revoked: list[CredentialHandle] = []
            for handle in candidates:
                self._provider.revoke(handle.provider_ref)
                next_status = transition(
                    handle.status, "REVOKED", CREDENTIAL_HANDLE_TRANSITIONS
                )
                rowcount = await self._repository.update_fields(
                    active.connection,
                    handle.handle_id,
                    fields={
                        "status": next_status,
                        "revoked_at": now,
                        "revocation_reason": reason,
                        "updated_at": now,
                    },
                )
                if rowcount != 1:
                    raise DdeError(
                        "VERSION_CONFLICT",
                        "Unknown credential handle",
                        details={"handle_id": str(handle.handle_id)},
                    )
                updated = await self._require_handle(active, handle.handle_id)
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="CredentialEmergencyRevoked",
                    aggregate_type="credential_handle",
                    aggregate_id=updated.handle_id,
                    mission_id=updated.mission_id,
                    task_id=updated.task_id,
                    payload={"reason": reason},
                    uow=active,
                )
                revoked.append(updated)
            return revoked

        return await self._run(uow, tenant_id, project_id, _op)

    async def inspect(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        lease_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[CredentialHandle]:
        """Chapter 14.3's `inspect(lease)`: "Returns non-secret metadata
        only: provider, scope, expiry, status, policy version." Every
        field on a persisted `CredentialHandle` already satisfies this --
        `secret_hash` is a one-way digest, never the secret itself
        (Chapter 14.3: "Audit records store metadata and hashes, never
        secret material") -- so this is a plain, unfiltered read of every
        handle ever issued against the lease."""

        async def _op(active: PostgresUnitOfWork) -> list[CredentialHandle]:
            return await self._repository.list_for_lease(active.connection, lease_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_handle(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        handle_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> CredentialHandle:
        async def _op(active: PostgresUnitOfWork) -> CredentialHandle:
            return await self._require_handle(active, handle_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def verify(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        handle_id: UUID,
        secret_value: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> bool:
        """Not a Chapter 14.3-named operation. The chapter never enumerates
        a verify/authenticate call because that belongs to whatever real
        caller ends up consuming a brokered credential (Chapter 7.2's T1
        gateway would call the equivalent per invocation) -- Stage 1 has no
        such caller yet (this mission's own scoping finding). Without a
        real way to check a presented secret against a handle's live
        state, "expires" and "revoked" would be status columns nobody ever
        reads -- not a provable security mechanic. Compares against the
        stored `secret_hash` only, in constant time; the raw value this
        method is handed is never persisted by this call."""

        async def _op(active: PostgresUnitOfWork) -> bool:
            handle = await self._repository.get_by_id(active.connection, handle_id)
            if handle is None:
                return False
            if handle.status not in LIVE_HANDLE_STATUSES:
                return False
            if handle.expires_at <= self._clock.now():
                return False
            return hmac.compare_digest(handle.secret_hash, sha256_hex(secret_value))

        return await self._run(uow, tenant_id, project_id, _op)

    async def _require_active_lease(
        self, active: PostgresUnitOfWork, lease_id: UUID
    ) -> CapabilityLease:
        """Chapter 14.3's "policy and lease validation", live and
        fail-closed: a credential is issued only against a lease whose
        current, freshly-read `status` is literally `ACTIVE` (Chapter 9.2)
        and whose `expires_at` has not yet passed -- a `GRANTED` (never
        activated), `DENIED`, `REVOKED`, `EXPIRED` or `CONSUMED` lease is
        denied identically, and a lease unknown to this tenant/project (RLS
        filters it to `None`) is denied the same way."""
        lease = await self._lease_repository.get_by_id(active.connection, lease_id)
        if lease is None:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown capability lease -- fail closed",
                details={"lease_id": str(lease_id)},
            )
        if lease.status != "ACTIVE":
            raise DdeError(
                "POLICY_DENIED",
                f"Capability lease is {lease.status}, not ACTIVE -- "
                "credential issuance denied",
                details={"lease_id": str(lease_id), "status": lease.status},
            )
        if lease.expires_at <= self._clock.now():
            raise DdeError(
                "POLICY_DENIED",
                "Capability lease has expired -- credential issuance denied",
                details={"lease_id": str(lease_id)},
            )
        return lease

    async def _require_handle(
        self, active: PostgresUnitOfWork, handle_id: UUID
    ) -> CredentialHandle:
        record = await self._repository.get_by_id(active.connection, handle_id)
        if record is None:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown credential handle",
                details={"handle_id": str(handle_id)},
            )
        return record

    def _replay_or_raise(self, record: CommandIdempotency) -> IssuedCredential:
        """See module docstring: a replay can only ever return the
        already-issued handle's metadata, never the original secret."""
        if record.status == "completed" and record.result is not None:
            handle = CredentialHandle.model_validate(record.result)
            return IssuedCredential(handle=handle, secret_value=None)
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


def _scope_for(lease: CapabilityLease) -> CredentialScope:
    return CredentialScope(
        tenant_id=lease.tenant_id,
        project_id=lease.project_id,
        mission_id=lease.mission_id,
        task_id=lease.task_id,
        lease_id=lease.lease_id,
        capability_id=lease.capability_id,
        resource_scope=lease.resource_scope,
    )
