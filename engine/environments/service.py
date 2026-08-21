"""Production Provisioner — the sole writer of `execution_environments` rows
in PostgreSQL (Chapter 3.5, 3.8, 7.3, 7.4).

`ExecutionEnvironmentService.provision()` drives the real `PROVISIONING ->
READY | FAILED` half of Chapter 7.3's lifecycle against a real
`EnvironmentBackend` (Chapter 7's substrate abstraction); `transition()`
drives the rest (`READY -> ACTIVE -> DRAINING -> RETIRED`, and the `any ->
FAILED -> REPAIRING | REPLACEMENT` branch) under the same optimistic-locking
discipline `engine.missions.service.MissionService.transition_mission` uses.

**DDE-029 (Chapter 7.4 warm pool).** `acquire()` / `release()` / `top_up()`
implement the provisioning-economics rules this module previously deferred:

- *Warm pool*: `top_up()` maintains `DEFAULT_WARM_POOL_SIZE` READY
  environments per `(class, image_digest)` tuple per project; `acquire()`
  reuses a pooled environment (warm hit) before cold-provisioning.
- *Image discipline*: the pool is keyed on `image_digest`; a toolchain change
  yields a new digest, and `top_up()` retires pooled environments whose stored
  digest no longer matches (Chapter 8.5 re-certification of worker profiles is
  out of this module's scope).
- *Reuse policy*: `release()` returns an environment to the pool only when the
  caller asserts the workspace was destroyed and the environment never carried
  credential material (`credential_profile_id IS NULL` — the append-only
  credential binding, so a non-NULL value means "credential material was ever
  present"). Cross-tenant reuse is impossible: every pooled read is scoped to
  `(tenant_id, project_id)` and the transaction runs under Chapter 3.2 RLS.
- *Economics*: cold-provision latency is measured and recorded on the
  `ExecutionEnvironmentReady` / `ExecutionEnvironmentAcquired` events; a cold
  provision above `cold_provision_threshold_ms` (default 45 s) also emits
  `ExecutionEnvironmentSlowProvision` — the durable signal a §16.4 overhead
  budget and an ops pager consume. Aggregation into the per-mission overhead
  budget and CPU-seconds accounting are DDE-041 (Chapter 16.4) and are
  *not* implemented here.

Every backend except `local_process` remains unbuilt
(`docker`/`microvm`/`vm`/`device`/`ci_runner`/`remote_api` — Chapter 7.2's T2
containment needs a container/microVM backend this mission does not build;
see `engine.environments.backends`). The `local_process` backend's `teardown`
is a no-op (no persistent OS resource), so "destroyed after its run unless
pooled" is represented durably by the `RETIRED` lifecycle state; a real
container backend (future) would release resources at the same call site.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.execution_environment import ExecutionEnvironment
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.environments.backends.base import (
    EnvironmentBackend,
    EnvironmentSpec,
    IsolationReport,
)
from engine.environments.backends.local_process import LocalProcessBackend
from engine.environments.repository import ExecutionEnvironmentRepository
from engine.environments.states import ENVIRONMENT_TRANSITIONS, NOT_SCHEDULABLE
from engine.events.service import EventService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

EnvironmentClass = Literal[
    "research", "development", "security", "staging", "production"
]

#: Chapter 7.4: "Maintain N ready environments per common (class, image_digest)
#: tuple. Default N=2 per active project."
DEFAULT_WARM_POOL_SIZE = 2

#: Chapter 7.4: "Cold provisioning above the policy threshold (default 45 s)
#: raises an operational alert."
DEFAULT_COLD_PROVISION_THRESHOLD_MS = 45_000


@dataclass(frozen=True)
class AcquiredEnvironment:
    """Result of `acquire()`: the environment, whether it came from the warm
    pool, and the cold-provision latency in milliseconds (`None` for a warm
    hit, where nothing was provisioned)."""

    environment: ExecutionEnvironment
    reused: bool
    provisioning_ms: int | None


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
        cold_provision_threshold_ms: int = DEFAULT_COLD_PROVISION_THRESHOLD_MS,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._repository = repository or ExecutionEnvironmentRepository()
        self._clock = clock or SystemClock()
        self._backend: EnvironmentBackend = backend or LocalProcessBackend()
        self._cold_provision_threshold_ms = cold_provision_threshold_ms

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

    def _resolve_report(self, spec: EnvironmentSpec) -> tuple[IsolationReport, int]:
        """Run the backend's real `provision()` once and return its honest
        `IsolationReport` plus the elapsed wall-clock time in milliseconds.

        This is the Chapter 7.4 cold-provision latency: for `local_process`
        the call is a stateless metadata computation, but a real container
        backend (future) would do its image pull here, and that latency is
        what the 45 s threshold guards. May raise `OSError` — callers decide
        whether that is a digest-resolution failure (no environment exists
        yet) or a provision failure (a `PROVISIONING` row already exists and
        must be marked `FAILED`)."""
        started = time.monotonic()
        handle = self._backend.provision(spec)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return handle.report, elapsed_ms

    async def _insert_provisioning(
        self,
        active: PostgresUnitOfWork,
        *,
        tenant_id: UUID,
        project_id: UUID,
        environment_class: EnvironmentClass,
        resource_limits: dict[str, object],
        network_policy: dict[str, object],
        filesystem_policy: dict[str, object],
    ) -> UUID:
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
        return environment_id

    async def _apply_ready(
        self,
        active: PostgresUnitOfWork,
        *,
        tenant_id: UUID,
        project_id: UUID,
        environment_id: UUID,
        report: IsolationReport,
        provisioning_ms: int,
    ) -> ExecutionEnvironment:
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
                "provisioning_ms": provisioning_ms,
            },
            uow=active,
        )
        return updated

    async def _mark_failed(
        self,
        active: PostgresUnitOfWork,
        *,
        tenant_id: UUID,
        project_id: UUID,
        environment_id: UUID,
        reason: str,
    ) -> None:
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
            payload={"reason": reason},
            uow=active,
        )

    async def _advance(
        self,
        active: PostgresUnitOfWork,
        *,
        environment: ExecutionEnvironment,
        target_lifecycle_state: str,
    ) -> ExecutionEnvironment:
        """One lock-guarded lifecycle transition (Chapter 3.5), emitting the
        shared `ExecutionEnvironmentTransitioned` event. Used by the warm-pool
        claim, release and retire paths; `transition()` (the public, explicit
        API) keeps its own separate implementation."""
        if environment.lifecycle_state == target_lifecycle_state:
            return environment
        next_state = transition(
            environment.lifecycle_state, target_lifecycle_state, ENVIRONMENT_TRANSITIONS
        )
        now = self._clock.now()
        rowcount = await self._repository.update_environment(
            active.connection,
            environment.environment_id,
            expected_lock_version=environment.lock_version,
            updated_at=now,
            fields={"lifecycle_state": next_state},
        )
        if rowcount != 1:
            refreshed = await self._require_environment(
                active, environment.environment_id
            )
            raise DdeError(
                "VERSION_CONFLICT",
                "ExecutionEnvironment lock_version mismatch",
                retryable=True,
                details={
                    "expected": environment.lock_version,
                    "actual": refreshed.lock_version,
                },
            )
        updated = await self._require_environment(active, environment.environment_id)
        await self._events.append(
            tenant_id=environment.tenant_id,
            project_id=environment.project_id,
            event_type="ExecutionEnvironmentTransitioned",
            aggregate_type="execution_environment",
            aggregate_id=environment.environment_id,
            payload={
                "from": environment.lifecycle_state,
                "to": updated.lifecycle_state,
            },
            uow=active,
        )
        return updated

    async def _claim(
        self, active: PostgresUnitOfWork, environment: ExecutionEnvironment
    ) -> ExecutionEnvironment:
        return await self._advance(
            active, environment=environment, target_lifecycle_state="ACTIVE"
        )

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
        planner step "select a compatible environment"). Inserts a real
        `PROVISIONING` row, calls the real backend, then moves the same row
        to `READY` — or, on a genuine backend failure, to `FAILED` — as a
        second, lock-guarded update. Never raises an unhandled exception:
        a backend failure is caught, persisted as a real `FAILED` row, and
        re-raised as a typed `ENVIRONMENT_FAILED` `DdeError`. Cold-provision
        latency is recorded on the Ready event."""

        async def _op(active: PostgresUnitOfWork) -> ExecutionEnvironment:
            environment_id = await self._insert_provisioning(
                active,
                tenant_id=tenant_id,
                project_id=project_id,
                environment_class=environment_class,
                resource_limits=resource_limits,
                network_policy=network_policy,
                filesystem_policy=filesystem_policy,
            )
            spec = EnvironmentSpec(
                environment_class=environment_class,
                resource_limits=resource_limits,
                network_policy=network_policy,
                filesystem_policy=filesystem_policy,
            )
            try:
                report, provisioning_ms = self._resolve_report(spec)
            except OSError as exc:
                await self._mark_failed(
                    active,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    environment_id=environment_id,
                    reason=str(exc),
                )
                raise DdeError(
                    "ENVIRONMENT_FAILED",
                    "Environment provisioning failed",
                    details={"environment_id": str(environment_id), "reason": str(exc)},
                ) from exc
            return await self._apply_ready(
                active,
                tenant_id=tenant_id,
                project_id=project_id,
                environment_id=environment_id,
                report=report,
                provisioning_ms=provisioning_ms,
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def acquire(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        environment_class: EnvironmentClass,
        resource_limits: dict[str, object],
        network_policy: dict[str, object],
        filesystem_policy: dict[str, object],
        uow: PostgresUnitOfWork | None = None,
    ) -> AcquiredEnvironment:
        """Chapter 7.4 warm-pool acquisition: reuse a pooled READY environment
        for the current `(class, image_digest)` tuple if one exists, otherwise
        cold-provision. Returns the environment in `ACTIVE` (leased) state.

        Cross-tenant reuse is impossible: the pooled read is scoped to
        `(tenant_id, project_id)` and runs inside the Chapter 3.2 RLS
        transaction. A digest-resolution failure (backend raises) is a typed
        `ENVIRONMENT_FAILED` with no persisted row — nothing was provisioned,
        unlike `provision()`, which persists a `FAILED` row for a specific
        environment."""

        async def _op(active: PostgresUnitOfWork) -> AcquiredEnvironment:
            spec = EnvironmentSpec(
                environment_class=environment_class,
                resource_limits=resource_limits,
                network_policy=network_policy,
                filesystem_policy=filesystem_policy,
            )
            try:
                report, provisioning_ms = self._resolve_report(spec)
            except OSError as exc:
                raise DdeError(
                    "ENVIRONMENT_FAILED",
                    "Cannot resolve environment image digest",
                    details={"class": environment_class, "reason": str(exc)},
                ) from exc
            pooled = await self._repository.list_pooled_for_digest(
                active.connection,
                tenant_id=tenant_id,
                project_id=project_id,
                environment_class=environment_class,
                image_digest=report.image_digest,
                limit=1,
            )
            if pooled:
                claimed = await self._claim(active, pooled[0])
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="ExecutionEnvironmentAcquired",
                    aggregate_type="execution_environment",
                    aggregate_id=claimed.environment_id,
                    payload={"reused": True, "provisioning_ms": None},
                    uow=active,
                )
                return AcquiredEnvironment(
                    environment=claimed, reused=True, provisioning_ms=None
                )
            environment_id = await self._insert_provisioning(
                active,
                tenant_id=tenant_id,
                project_id=project_id,
                environment_class=environment_class,
                resource_limits=resource_limits,
                network_policy=network_policy,
                filesystem_policy=filesystem_policy,
            )
            ready = await self._apply_ready(
                active,
                tenant_id=tenant_id,
                project_id=project_id,
                environment_id=environment_id,
                report=report,
                provisioning_ms=provisioning_ms,
            )
            acquired = await self._claim(active, ready)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ExecutionEnvironmentAcquired",
                aggregate_type="execution_environment",
                aggregate_id=acquired.environment_id,
                payload={"reused": False, "provisioning_ms": provisioning_ms},
                uow=active,
            )
            if provisioning_ms > self._cold_provision_threshold_ms:
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="ExecutionEnvironmentSlowProvision",
                    aggregate_type="execution_environment",
                    aggregate_id=acquired.environment_id,
                    payload={
                        "provisioning_ms": provisioning_ms,
                        "threshold_ms": self._cold_provision_threshold_ms,
                    },
                    uow=active,
                )
            return AcquiredEnvironment(
                environment=acquired, reused=False, provisioning_ms=provisioning_ms
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def release(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        environment_id: UUID,
        workspace_destroyed: bool,
        lock_version: int,
        uow: PostgresUnitOfWork | None = None,
    ) -> ExecutionEnvironment:
        """Chapter 7.4 reuse policy, enforced at the release call site.

        Returns the environment to the warm pool (`ACTIVE -> READY`) only when
        the caller asserts the workspace was destroyed and the environment
        never carried credential material (`credential_profile_id IS NULL` —
        the append-only credential binding, so a non-NULL value means
        credential material was ever present). Otherwise it is destroyed
        (`ACTIVE -> DRAINING -> RETIRED`): Chapter 7.4 "Destroyed after its
        run unless pooled."

        `workspace_destroyed=True` must only be passed after
        `WorkspaceService.cleanup()` has removed the workspace. The production
        caller that composes workspace cleanup with this release — at
        `TaskAttempt` finalization (`finalize`/`fail`, after verification) — is
        deferred: the environment lease spans the full attempt lifecycle
        (plan → worker runs → verification), which crosses DDE-012
        (verification) and DDE-023 (attempt durability) rather than this
        warm-pool mission. `workspace_destroyed` is the honest seam that
        future caller wires through."""

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
            if current.lifecycle_state != "ACTIVE":
                raise DdeError(
                    "ENVIRONMENT_FAILED",
                    f"Environment is {current.lifecycle_state}, not ACTIVE; "
                    "cannot release",
                    details={"environment_id": str(environment_id)},
                )
            reusable = workspace_destroyed and current.credential_profile_id is None
            if reusable:
                pooled = await self._advance(
                    active, environment=current, target_lifecycle_state="READY"
                )
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="ExecutionEnvironmentPooled",
                    aggregate_type="execution_environment",
                    aggregate_id=environment_id,
                    payload={"reused": True},
                    uow=active,
                )
                return pooled
            draining = await self._advance(
                active, environment=current, target_lifecycle_state="DRAINING"
            )
            return await self._advance(
                active, environment=draining, target_lifecycle_state="RETIRED"
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def top_up(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        environment_class: EnvironmentClass,
        resource_limits: dict[str, object],
        network_policy: dict[str, object],
        filesystem_policy: dict[str, object],
        target_size: int = DEFAULT_WARM_POOL_SIZE,
        uow: PostgresUnitOfWork | None = None,
    ) -> int:
        """Chapter 7.4 warm-pool maintenance and image discipline.

        Retires pooled environments whose stored `image_digest` no longer
        matches the current digest (a toolchain change produces a new digest),
        then cold-provisions until `target_size` pooled READY environments
        exist for the current digest. Returns the number newly provisioned.
        `provisioning_ms` on those rows is `0`: their provisioning is
        amortized ahead-of-demand maintenance, not the on-demand cold
        provision the 45 s threshold guards."""

        async def _op(active: PostgresUnitOfWork) -> int:
            spec = EnvironmentSpec(
                environment_class=environment_class,
                resource_limits=resource_limits,
                network_policy=network_policy,
                filesystem_policy=filesystem_policy,
            )
            try:
                report, _ms = self._resolve_report(spec)
            except OSError as exc:
                raise DdeError(
                    "ENVIRONMENT_FAILED",
                    "Cannot resolve environment image digest",
                    details={"class": environment_class, "reason": str(exc)},
                ) from exc
            stale = await self._repository.list_pooled_for_class(
                active.connection,
                tenant_id=tenant_id,
                project_id=project_id,
                environment_class=environment_class,
            )
            for environment in stale:
                if environment.image_digest != report.image_digest:
                    draining = await self._advance(
                        active,
                        environment=environment,
                        target_lifecycle_state="DRAINING",
                    )
                    await self._advance(
                        active, environment=draining, target_lifecycle_state="RETIRED"
                    )
            current_count = await self._repository.count_pooled_for_digest(
                active.connection,
                tenant_id=tenant_id,
                project_id=project_id,
                environment_class=environment_class,
                image_digest=report.image_digest,
            )
            created = 0
            while current_count + created < target_size:
                environment_id = await self._insert_provisioning(
                    active,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    environment_class=environment_class,
                    resource_limits=resource_limits,
                    network_policy=network_policy,
                    filesystem_policy=filesystem_policy,
                )
                await self._apply_ready(
                    active,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    environment_id=environment_id,
                    report=report,
                    provisioning_ms=0,
                )
                created += 1
            return created

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
