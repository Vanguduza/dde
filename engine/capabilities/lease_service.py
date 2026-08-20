"""Production `CapabilityLease` service (Chapter 9.2) -- the sole writer of
`capability_leases` rows in PostgreSQL (Chapter 3.5, 3.8).

**What this is.** The real authority boundary Chapter 9.2 describes:
`request()` evaluates a caller's declared `(capability_id, capability_version)`
against the real, `engine.capabilities`-owned `CapabilityDescriptor` catalog
(DDE-016) and grants or denies a lease accordingly -- "lease denial is a
normal control outcome, not an error" (9.2), so a denial is a real, durable
`DENIED` row returned to the caller, not an exception. `require_active` is
the Chapter 7.2 T1 "brokered" enforcement guard: the one, small, centralised
check `engine.workers.scripted_adapter.ScriptedWorkerAdapter` and
`engine.workspaces.service.WorkspaceService.snapshot` call before performing
their real side effect. `revoke` implements Chapter 9.2's "expired and
revoked leases fail closed at the enforcement boundary" -- a lease revoked
between two gated calls in the same run denies the next one, which is this
mission's real, achievable granularity for "lease revocation mid-run fails
closed" (S2's exit-gate fixture, AGENTS.md/Chapter 18.2 section 18.2): there
is no per-syscall interception without T2 containment (DDE-018), so
revocation is observed at the next discrete `require_active` call, not
inside an already-in-flight uninterruptible subprocess.

**CapabilityLease vs WriteScopeLease.** Chapter 9.2's `CapabilityLease`
decides *whether a caller may invoke a capability at all* -- tenant/mission/
task/plan/run-scoped authority over an operation class. Chapter 10.3's
`WriteScopeLease` (`engine.integration`) decides *which file paths an
already-authorised operation may touch* -- a structural conflict-prevention
mechanism for concurrent workers writing to one repository. They compose (a
worker's write still needs both: a granted `capability.workspace_filesystem`
lease to write at all, and its task's `WriteScopeLease` to cover the path it
writes to) but are neither the same mechanism nor interchangeable; this
service never reads or writes `write_scope_leases`.

**Idempotency (AGENTS.md's Definition of Done).** `request()` is guarded by
`engine.events.idempotency.CommandLedger` on a caller-supplied
`idempotency_key` -- the same durable-identity mechanism
`engine.workers.service.WorkerManagerService.invoke_run` already uses, not a
second one invented for this module. A repeated `request()` call with the
same key never re-evaluates or re-grants; it returns the first call's stored
lease.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.lease_hashing import lease_hash
from engine.capabilities.lease_repository import CapabilityLeaseRepository
from engine.capabilities.lease_states import (
    CAPABILITY_LEASE_TRANSITIONS,
    HELD_LEASE_STATUSES,
)
from engine.capabilities.service import CapabilityRegistryService
from engine.contracts.capability_lease import CapabilityLease
from engine.contracts.command_idempotency import CommandIdempotency
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

#: This service's own policy version (Chapter 6.2's `POLICY_VERSION` /
#: `engine.workers.service.WORKER_MANAGER_POLICY_VERSION` naming
#: convention) -- no chapter names a literal value for CapabilityLease's
#: `issued_by_policy_version`.
CAPABILITY_LEASE_POLICY_VERSION = "capability-lease-v1"

#: Chapter 9.2: "expires by default". No chapter names a concrete TTL for a
#: CapabilityLease (unlike `command_idempotency`'s explicit 30-day rule,
#: Chapter 3.7); this mirrors `engine.integration.service.
#: WriteScopeLeaseService`'s own `DEFAULT_LEASE_TTL` choice for the
#: analogous gap.
DEFAULT_LEASE_TTL = timedelta(hours=24)


class CapabilityLeaseService:
    """Async, PostgreSQL-backed writer for `capability_leases` (Chapter
    3.8: "Status only; scope immutable"). Each public method opens and
    commits its own unit of work unless one is supplied, so a caller
    composing a cross-module transaction (Chapter 3.5) can share it
    instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: CapabilityLeaseRepository | None = None,
        events: EventService | None = None,
        commands: CommandLedger | None = None,
        capabilities: CapabilityRegistryService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or CapabilityLeaseRepository()
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
        self._capabilities = capabilities or CapabilityRegistryService(
            engine, events=self._events
        )
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
            try:
                result = await body(owned)
            except Exception:
                # `require_active` durably marks a lease EXPIRED before
                # raising POLICY_DENIED (Chapter 9.2: expiry is a real,
                # observed transition, not merely an inferred one) --
                # that write must survive the exception, exactly like
                # `engine.workspaces.service.WorkspaceService._run`'s
                # identical "persist real evidence, then re-raise" pattern.
                await owned.commit()
                raise
            await owned.commit()
            return result

    async def request(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        task_id: UUID,
        execution_plan_id: UUID,
        capability_id: str,
        capability_version: str,
        requested_by: str,
        idempotency_key: str,
        worker_run_id: UUID | None = None,
        environment_id: UUID | None = None,
        resource_scope: dict[str, object] | None = None,
        operation_scope: str = "execute",
        constraints: dict[str, object] | None = None,
        issued_by_policy_version: str = CAPABILITY_LEASE_POLICY_VERSION,
        ttl: timedelta = DEFAULT_LEASE_TTL,
        uow: PostgresUnitOfWork | None = None,
    ) -> CapabilityLease:
        """Chapter 9.2's real grant decision: `REQUESTED -> EVALUATING ->
        GRANTED | DENIED`. Granting requires a real `CapabilityDescriptor`
        for `(capability_id, capability_version)` that is both
        `certification_status="CERTIFIED"` and `lifecycle_status="ACTIVE"`
        (Chapter 9.1/9.2) -- read via `engine.capabilities.service.
        CapabilityRegistryService.get_active`, never re-implemented here.
        A denial is returned, not raised (9.2: "not an error")."""
        resolved_resource_scope = dict(resource_scope or {})
        resolved_constraints = dict(constraints or {})
        digest = lease_hash(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            task_id=task_id,
            execution_plan_id=execution_plan_id,
            worker_run_id=worker_run_id,
            environment_id=environment_id,
            capability_id=capability_id,
            capability_version=capability_version,
            resource_scope=resolved_resource_scope,
            operation_scope=operation_scope,
            constraints=resolved_constraints,
        )

        async def _op(active: PostgresUnitOfWork) -> CapabilityLease:
            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=digest,
                uow=active,
            )
            if not is_new:
                return self._replay_or_raise(record)

            now = self._clock.now()
            requested = CapabilityLease(
                lease_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
                execution_plan_id=execution_plan_id,
                worker_run_id=worker_run_id,
                environment_id=environment_id,
                capability_id=capability_id,
                capability_version=capability_version,
                resource_scope=resolved_resource_scope,
                operation_scope=operation_scope,
                constraints=resolved_constraints,
                issued_by_policy_version=issued_by_policy_version,
                issued_at=now,
                expires_at=now + ttl,
                revocable=True,
                status="REQUESTED",
                denied_reason=None,
                revoked_at=None,
                revocation_reason=None,
                lease_hash=digest,
                requested_by=requested_by,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_lease(active.connection, requested)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="CapabilityLeaseRequested",
                aggregate_type="capability_lease",
                aggregate_id=requested.lease_id,
                mission_id=mission_id,
                task_id=task_id,
                payload={
                    "capability_id": capability_id,
                    "capability_version": capability_version,
                },
                uow=active,
            )

            evaluating = await self._transition(
                active,
                requested,
                "EVALUATING",
                event_type="CapabilityLeaseEvaluating",
                payload={},
            )

            denial_reason = await self._evaluate(
                active,
                tenant_id=tenant_id,
                project_id=project_id,
                capability_id=capability_id,
                capability_version=capability_version,
            )

            if denial_reason is not None:
                denied = await self._transition(
                    active,
                    evaluating,
                    "DENIED",
                    event_type="CapabilityLeaseDenied",
                    payload={"reason": denial_reason},
                    extra_fields={"denied_reason": denial_reason},
                )
                await self._commands.complete(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    command_id=record.command_id,
                    result=denied.model_dump(mode="json"),
                    uow=active,
                )
                return denied

            granted = await self._transition(
                active,
                evaluating,
                "GRANTED",
                event_type="CapabilityLeaseGranted",
                payload={
                    "capability_id": capability_id,
                    "capability_version": capability_version,
                },
            )
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=granted.model_dump(mode="json"),
                uow=active,
            )
            return granted

        return await self._run(uow, tenant_id, project_id, _op)

    async def _evaluate(
        self,
        active: PostgresUnitOfWork,
        *,
        tenant_id: UUID,
        project_id: UUID,
        capability_id: str,
        capability_version: str,
    ) -> str | None:
        """Returns a denial reason, or `None` if the request should be
        granted. Chapter 9.2's real decision logic: a lease may only be
        granted against the capability's currently `ACTIVE` descriptor
        version, itself `certification_status="CERTIFIED"`."""
        try:
            descriptor = await self._capabilities.get_active(
                tenant_id=tenant_id,
                project_id=project_id,
                capability_id=capability_id,
                uow=active,
            )
        except DdeError as exc:
            if exc.error_code != "POLICY_DENIED":
                raise
            return (
                f"no ACTIVE capability descriptor for capability_id={capability_id!r}"
            )
        if descriptor.version != capability_version:
            return (
                f"ACTIVE descriptor version is {descriptor.version!r}, "
                f"not the requested {capability_version!r}"
            )
        if descriptor.certification_status != "CERTIFIED":
            return (
                "descriptor certification_status is "
                f"{descriptor.certification_status!r}, not CERTIFIED"
            )
        if descriptor.lifecycle_status != "ACTIVE":
            return (
                f"descriptor lifecycle_status is {descriptor.lifecycle_status!r}, "
                "not ACTIVE"
            )
        return None

    async def require_active(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        worker_run_id: UUID,
        capability_id: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> CapabilityLease:
        """The T1 brokered enforcement guard (Chapter 7.2): "every call
        passes through the capability gateway: lease validated ... per
        call." Fails closed -- no lease, a denied/revoked/expired/consumed
        lease, or an expired-but-not-yet-marked lease all raise
        `POLICY_DENIED` rather than allowing the caller to proceed (Chapter
        9.2: "expired and revoked leases fail closed at the enforcement
        boundary even if the worker holds cached schemas"). The first
        successful check against a `GRANTED` lease marks it `ACTIVE`
        (Chapter 9.2's real state for "currently authorising an in-flight
        operation")."""

        async def _op(active: PostgresUnitOfWork) -> CapabilityLease:
            lease = await self._repository.get_active_for_run(
                active.connection,
                worker_run_id=worker_run_id,
                capability_id=capability_id,
            )
            if lease is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "No capability lease exists for this run and capability "
                    "-- fail closed",
                    details={
                        "worker_run_id": str(worker_run_id),
                        "capability_id": capability_id,
                    },
                )
            now = self._clock.now()
            if lease.status not in HELD_LEASE_STATUSES:
                raise DdeError(
                    "POLICY_DENIED",
                    f"Capability lease is {lease.status}, not held -- fail closed",
                    details={
                        "lease_id": str(lease.lease_id),
                        "status": lease.status,
                    },
                )
            if lease.expires_at <= now:
                await self._transition(
                    active,
                    lease,
                    "EXPIRED",
                    event_type="CapabilityLeaseTransitioned",
                    payload={"from": lease.status, "to": "EXPIRED"},
                )
                raise DdeError(
                    "POLICY_DENIED",
                    "Capability lease has expired -- fail closed",
                    details={"lease_id": str(lease.lease_id)},
                )
            if lease.status == "GRANTED":
                lease = await self._transition(
                    active,
                    lease,
                    "ACTIVE",
                    event_type="CapabilityLeaseActivated",
                    payload={},
                )
            return lease

        return await self._run(uow, tenant_id, project_id, _op)

    async def revoke(
        self,
        *,
        lease: CapabilityLease,
        reason: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> CapabilityLease:
        """Chapter 9.2: `GRANTED|ACTIVE -> REVOKED`. The revoked row is
        durable and carries `revocation_reason`; the NEXT `require_active`
        call for this run/capability fails closed against it."""

        async def _op(active: PostgresUnitOfWork) -> CapabilityLease:
            current = await self._require_lease(active, lease.lease_id)
            now = self._clock.now()
            updated = await self._transition(
                active,
                current,
                "REVOKED",
                event_type="CapabilityLeaseRevoked",
                payload={"reason": reason},
                extra_fields={"revoked_at": now, "revocation_reason": reason},
            )
            return updated

        return await self._run(uow, lease.tenant_id, lease.project_id, _op)

    async def consume(
        self,
        *,
        lease: CapabilityLease,
        uow: PostgresUnitOfWork | None = None,
    ) -> CapabilityLease:
        """Chapter 9.2: `ACTIVE -> CONSUMED`, once the run that held the
        lease reaches a terminal state."""

        async def _op(active: PostgresUnitOfWork) -> CapabilityLease:
            current = await self._require_lease(active, lease.lease_id)
            return await self._transition(
                active,
                current,
                "CONSUMED",
                event_type="CapabilityLeaseConsumed",
                payload={},
            )

        return await self._run(uow, lease.tenant_id, lease.project_id, _op)

    async def consume_all_for_run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        worker_run_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[CapabilityLease]:
        """Consumes every still-`ACTIVE` lease bound to a run once that run
        reaches a terminal state (Chapter 9.2's `ACTIVE -> CONSUMED`).
        Leases already `REVOKED`/`EXPIRED`/`DENIED` are left untouched --
        their terminal status already records what happened."""

        async def _op(active: PostgresUnitOfWork) -> list[CapabilityLease]:
            leases = await self._repository.list_for_run(
                active.connection, worker_run_id
            )
            consumed: list[CapabilityLease] = []
            for item in leases:
                if item.status != "ACTIVE":
                    continue
                updated = await self._transition(
                    active,
                    item,
                    "CONSUMED",
                    event_type="CapabilityLeaseConsumed",
                    payload={},
                )
                consumed.append(updated)
            return consumed

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_lease(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        lease_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> CapabilityLease:
        async def _op(active: PostgresUnitOfWork) -> CapabilityLease:
            return await self._require_lease(active, lease_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_for_run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        worker_run_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[CapabilityLease]:
        async def _op(active: PostgresUnitOfWork) -> list[CapabilityLease]:
            return await self._repository.list_for_run(active.connection, worker_run_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def _transition(
        self,
        active: PostgresUnitOfWork,
        current: CapabilityLease,
        target_status: str,
        *,
        event_type: str,
        payload: dict[str, object],
        extra_fields: dict[str, object] | None = None,
    ) -> CapabilityLease:
        next_status = transition(
            current.status, target_status, CAPABILITY_LEASE_TRANSITIONS
        )
        now = self._clock.now()
        fields: dict[str, object] = {
            "status": next_status,
            "updated_at": now,
            **(extra_fields or {}),
        }
        rowcount = await self._repository.update_fields(
            active.connection, current.lease_id, fields=fields
        )
        if rowcount != 1:
            raise DdeError(
                "VERSION_CONFLICT",
                "Unknown capability lease",
                details={"lease_id": str(current.lease_id)},
            )
        updated = await self._require_lease(active, current.lease_id)
        await self._events.append(
            tenant_id=updated.tenant_id,
            project_id=updated.project_id,
            event_type=event_type,
            aggregate_type="capability_lease",
            aggregate_id=updated.lease_id,
            mission_id=updated.mission_id,
            task_id=updated.task_id,
            payload=payload,
            uow=active,
        )
        return updated

    def _replay_or_raise(self, record: CommandIdempotency) -> CapabilityLease:
        if record.status == "completed" and record.result is not None:
            return CapabilityLease.model_validate(record.result)
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

    async def _require_lease(
        self, active: PostgresUnitOfWork, lease_id: UUID
    ) -> CapabilityLease:
        record = await self._repository.get_by_id(active.connection, lease_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown capability lease")
        return record
