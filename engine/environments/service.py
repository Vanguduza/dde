"""Production Provisioner — the sole writer of `execution_environments` rows
in PostgreSQL (Chapter 3.5, 3.8, 7.3, 7.4).

`ExecutionEnvironmentService.provision()` drives the real `PROVISIONING ->
READY | FAILED` half of Chapter 7.3's lifecycle against a real
`EnvironmentBackend` (Chapter 7's substrate abstraction); `transition()`
drives the rest (`READY -> ACTIVE -> DRAINING -> RETIRED`, and the `any ->
FAILED -> REPAIRING | REPLACEMENT` branch) under the same optimistic-locking
discipline `engine.missions.service.MissionService.transition_mission` uses.

Deliberately out of this mission's scope: Chapter 7.4's warm pool (`provision`
always provisions fresh — "provision-on-demand is sufficient for Stage 1" per
this mission's brief; pooling is DDE-029/S3) and every backend except
`local_process` (`docker`/`microvm`/`vm`/`device`/`ci_runner`/`remote_api` —
Chapter 7.2's T2 containment needs a container/microVM backend this mission
does not build; see `engine.environments.backends`).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.execution_environment import ExecutionEnvironment
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.environments.backends.base import EnvironmentBackend, EnvironmentSpec
from engine.environments.backends.local_process import LocalProcessBackend
from engine.environments.repository import ExecutionEnvironmentRepository
from engine.environments.states import ENVIRONMENT_TRANSITIONS, NOT_SCHEDULABLE
from engine.events.service import EventService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

EnvironmentClass = Literal[
    "research", "development", "security", "staging", "production"
]


class ExecutionEnvironmentService:
    """Async, PostgreSQL-backed writer for `execution_environments`
    (Chapter 3.8). Each public method opens and commits its own unit of
    work unless one is supplied, so a caller composing a cross-module
    transaction (Chapter 3.5) can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        repository: ExecutionEnvironmentRepository | None = None,
        clock: Clock | None = None,
        backend: EnvironmentBackend | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._repository = repository or ExecutionEnvironmentRepository()
        self._clock = clock or SystemClock()
        self._backend: EnvironmentBackend = backend or LocalProcessBackend()

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
                # A genuine provisioning failure already persisted its own
                # real FAILED row and event inside this same transaction
                # (Chapter 19.1's "captured as a real, persisted row" negative
                # test requirement) — commit that durable evidence instead of
                # discarding it, then let the typed error propagate.
                await owned.commit()
                raise
            await owned.commit()
            return result

    async def provision(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        environment_class: EnvironmentClass,
        resource_limits: dict[str, object],
        network_policy: dict[str, object],
        filesystem_policy: dict[str, object],
        uow: PostgresUnitOfWork | None = None,
    ) -> ExecutionEnvironment:
        """Provision a fresh `local` `ExecutionEnvironment` (Chapter 7.1's
        planner step "select a compatible environment" — Stage 1 has no
        warm pool, so "select" means "provision-on-demand"). Inserts a real
        `PROVISIONING` row, calls the real backend, then moves the same row
        to `READY` — or, on a genuine backend failure, to `FAILED` — as a
        second, lock-guarded update. Never raises an unhandled exception:
        a backend failure is caught, persisted as a real `FAILED` row, and
        re-raised as a typed `ENVIRONMENT_FAILED` `DdeError`."""

        async def _op(active: PostgresUnitOfWork) -> ExecutionEnvironment:
            environment_id = uuid7()
            now = self._clock.now()
            provisioning = ExecutionEnvironment(
                environment_id=environment_id,
                tenant_id=tenant_id,
                project_id=project_id,
                class_=environment_class,
                type="local",
                os_family="unknown",
                architecture="unknown",
                runtime_image="pending",
                image_digest="pending",
                toolchain_manifest={},
                toolchain_manifest_hash="pending",
                resource_limits=resource_limits,
                network_policy=network_policy,
                filesystem_policy=filesystem_policy,
                isolation_level="process",
                capability_compatibility={"backend": "local_process"},
                worker_compatibility={},
                status="provisioning",
                health_status="unknown",
                lifecycle_state="PROVISIONING",
                lock_version=1,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_environment(active.connection, provisioning)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ExecutionEnvironmentProvisioning",
                aggregate_type="execution_environment",
                aggregate_id=environment_id,
                payload={"class": environment_class, "type": "local"},
                uow=active,
            )

            spec = EnvironmentSpec(
                environment_class=environment_class,
                resource_limits=resource_limits,
                network_policy=network_policy,
                filesystem_policy=filesystem_policy,
            )
            try:
                handle = self._backend.provision(spec)
            except OSError as exc:
                failed_at = self._clock.now()
                await self._repository.update_environment(
                    active.connection,
                    environment_id,
                    expected_lock_version=1,
                    updated_at=failed_at,
                    fields={
                        "status": "failed",
                        "health_status": "unhealthy",
                        "lifecycle_state": "FAILED",
                    },
                )
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="ExecutionEnvironmentFailed",
                    aggregate_type="execution_environment",
                    aggregate_id=environment_id,
                    payload={"reason": str(exc)},
                    uow=active,
                )
                raise DdeError(
                    "ENVIRONMENT_FAILED",
                    "Environment provisioning failed",
                    details={"environment_id": str(environment_id), "reason": str(exc)},
                ) from exc

            report = handle.report
            ready_at = self._clock.now()
            rowcount = await self._repository.update_environment(
                active.connection,
                environment_id,
                expected_lock_version=1,
                updated_at=ready_at,
                fields={
                    "os_family": report.os_family,
                    "architecture": report.architecture,
                    "runtime_image": report.runtime_image,
                    "image_digest": report.image_digest,
                    "toolchain_manifest": report.toolchain_manifest,
                    "toolchain_manifest_hash": report.toolchain_manifest_hash,
                    "isolation_level": report.isolation_level,
                    "network_policy": report.network_policy,
                    "filesystem_policy": report.filesystem_policy,
                    "status": "ready",
                    "health_status": "healthy",
                    "lifecycle_state": "READY",
                },
            )
            if rowcount != 1:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "ExecutionEnvironment lock_version mismatch during provisioning",
                    retryable=True,
                    details={"environment_id": str(environment_id)},
                )
            updated = await self._require_environment(active, environment_id)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ExecutionEnvironmentReady",
                aggregate_type="execution_environment",
                aggregate_id=environment_id,
                payload={
                    "image_digest": updated.image_digest,
                    "isolation_gaps": list(report.gaps),
                },
                uow=active,
            )
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def transition(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        environment_id: UUID,
        target_lifecycle_state: str,
        lock_version: int,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExecutionEnvironment:
        """Move `lifecycle_state` along Chapter 7.3's real state machine
        (`READY -> ACTIVE -> DRAINING -> RETIRED`, `any -> FAILED ->
        REPAIRING | REPLACEMENT`), guarded by `lock_version` (Chapter
        3.5)."""

        async def _op(active: PostgresUnitOfWork) -> ExecutionEnvironment:
            current = await self._require_environment(active, environment_id)
            if current.lock_version != lock_version:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "ExecutionEnvironment lock_version mismatch",
                    retryable=True,
                    details={
                        "expected": lock_version,
                        "actual": current.lock_version,
                    },
                )
            next_state = transition(
                current.lifecycle_state, target_lifecycle_state, ENVIRONMENT_TRANSITIONS
            )
            now = self._clock.now()
            rowcount = await self._repository.update_environment(
                active.connection,
                environment_id,
                expected_lock_version=lock_version,
                updated_at=now,
                fields={"lifecycle_state": next_state},
            )
            if rowcount != 1:
                refreshed = await self._require_environment(active, environment_id)
                raise DdeError(
                    "VERSION_CONFLICT",
                    "ExecutionEnvironment lock_version mismatch",
                    retryable=True,
                    details={
                        "expected": lock_version,
                        "actual": refreshed.lock_version,
                    },
                )
            updated = await self._require_environment(active, environment_id)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ExecutionEnvironmentTransitioned",
                aggregate_type="execution_environment",
                aggregate_id=environment_id,
                payload={
                    "from": current.lifecycle_state,
                    "to": updated.lifecycle_state,
                },
                uow=active,
            )
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_environment(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        environment_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExecutionEnvironment:
        async def _op(active: PostgresUnitOfWork) -> ExecutionEnvironment:
            return await self._require_environment(active, environment_id)

        return await self._run(uow, tenant_id, project_id, _op)

    def assert_schedulable(self, environment: ExecutionEnvironment) -> None:
        """Chapter 7.4: "No run is scheduled into `DRAINING` or `FAILED`."""
        if environment.lifecycle_state in NOT_SCHEDULABLE:
            raise DdeError(
                "ENVIRONMENT_FAILED",
                f"Environment is {environment.lifecycle_state}, not schedulable",
                details={"environment_id": str(environment.environment_id)},
            )

    async def _require_environment(
        self, active: PostgresUnitOfWork, environment_id: UUID
    ) -> ExecutionEnvironment:
        record = await self._repository.get_environment(
            active.connection, environment_id
        )
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown execution environment")
        return record
