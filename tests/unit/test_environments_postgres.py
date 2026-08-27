"""PostgreSQL-backed `engine.environments`: schema, state-transition and
negative tests (Chapter 19.1). Exercises `engine.environments.service.
ExecutionEnvironmentService`, the production writer of
`execution_environments` (Chapter 3.8), against a real database and the
real `LocalProcessBackend` (Chapter 7.3 `type = "local"`)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from uuid import UUID

import pytest

from engine.core.errors import DdeError
from engine.environments.backends.base import (
    EnvironmentSpec,
    IsolationReport,
    ProvisionedEnvironment,
)
from engine.environments.backends.local_process import LocalProcessBackend
from engine.environments.repository import ExecutionEnvironmentRepository
from engine.environments.service import (
    DEFAULT_WARM_POOL_SIZE,
    ExecutionEnvironmentService,
    ReplacedEnvironment,
)
from engine.events.repository import EventsRepository
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine, seed_tenant


class _FailingBackend:
    """A real `EnvironmentBackend` implementation whose `provision()`
    genuinely raises — not a mock of `LocalProcessBackend`, a second, real
    implementation of the same Protocol used to exercise the negative
    path."""

    def provision(self, spec: EnvironmentSpec) -> ProvisionedEnvironment:
        raise OSError("simulated provisioning failure")

    def run(self, *, cwd: Path, command: list[str], timeout_seconds: float) -> object:
        raise AssertionError("run() must not be called on a failed environment")

    def teardown(self, handle: ProvisionedEnvironment) -> None:
        return None


class _ScriptedBackend:
    """A real `EnvironmentBackend` with a configurable `image_digest` and an
    optional per-`provision()` delay — used to exercise Chapter 7.4's image
    discipline (a digest change retires the old pool) and the 45 s
    slow-provision alert threshold, without sleeping for 45 real seconds."""

    def __init__(self, digest: str, delay_ms: float = 0) -> None:
        self.digest = digest
        self.delay_ms = delay_ms

    def provision(self, spec: EnvironmentSpec) -> ProvisionedEnvironment:
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        report = IsolationReport(
            os_family="scripted",
            architecture="scripted",
            runtime_image="scripted",
            image_digest=self.digest,
            toolchain_manifest={},
            toolchain_manifest_hash="scripted",
            isolation_level="process",
            network_policy={},
            filesystem_policy={},
            gaps=(),
        )
        return ProvisionedEnvironment(environment_id_hint="scripted", report=report)

    def run(self, *, cwd: Path, command: list[str], timeout_seconds: float) -> object:
        raise AssertionError("run() must not be called on a scripted environment")

    def teardown(self, handle: ProvisionedEnvironment) -> None:
        return None


@pytest.mark.asyncio
async def test_schema_round_trip_persists_declared_columns() -> None:
    """A `execution_environments` row read back from the real table
    validates against the JSON-schema-generated contract (Chapter 3.1) —
    the schema test."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ExecutionEnvironmentService(engine)

        environment = await service.provision(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={"cpu_seconds": 60, "memory_mb": 512},
            network_policy={"mode": "unenforced"},
            filesystem_policy={"workspace_root_only": True},
        )

        assert environment.class_ == "development"
        assert environment.type == "local"
        assert environment.lifecycle_state == "READY"
        assert environment.runtime_image == "local-process"
        assert environment.image_digest.startswith("sha256:")
        assert environment.toolchain_manifest["python_version"]
        assert environment.lock_version == 2  # PROVISIONING (1) -> READY (2)

        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            reloaded = await ExecutionEnvironmentRepository().get_environment(
                uow.connection, environment.environment_id
            )
            await uow.commit()
        assert reloaded == environment
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_state_transition_ready_active_draining_retired() -> None:
    """Chapter 7.3: "PROVISIONING -> READY -> ACTIVE -> DRAINING ->
    RETIRED" — the state-transition test, each step a real, lock-guarded
    PostgreSQL update."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ExecutionEnvironmentService(engine)
        environment = await service.provision(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
        assert environment.lifecycle_state == "READY"

        active = await service.transition(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_id=environment.environment_id,
            target_lifecycle_state="ACTIVE",
            lock_version=environment.lock_version,
        )
        assert active.lifecycle_state == "ACTIVE"
        assert active.lock_version == environment.lock_version + 1

        draining = await service.transition(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_id=environment.environment_id,
            target_lifecycle_state="DRAINING",
            lock_version=active.lock_version,
        )
        assert draining.lifecycle_state == "DRAINING"

        retired = await service.transition(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_id=environment.environment_id,
            target_lifecycle_state="RETIRED",
            lock_version=draining.lock_version,
        )
        assert retired.lifecycle_state == "RETIRED"

        with pytest.raises(DdeError) as excinfo:
            await service.transition(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                environment_id=environment.environment_id,
                target_lifecycle_state="ACTIVE",
                lock_version=retired.lock_version,
            )
        assert excinfo.value.error_code == "VERSION_CONFLICT"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_provisioning_failure_persists_a_real_failed_row() -> None:
    """Chapter 19.1's negative-test requirement: a genuine backend failure
    is captured as a real, persisted `FAILED` row and a typed
    `ENVIRONMENT_FAILED` error — never an unhandled exception."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ExecutionEnvironmentService(engine, backend=_FailingBackend())

        with pytest.raises(DdeError) as excinfo:
            await service.provision(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                environment_class="development",
                resource_limits={},
                network_policy={},
                filesystem_policy={},
            )
        assert excinfo.value.error_code == "ENVIRONMENT_FAILED"
        environment_id = excinfo.value.details["environment_id"]

        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            reloaded = await ExecutionEnvironmentRepository().get_environment(
                uow.connection, UUID(environment_id)
            )
            await uow.commit()
        assert reloaded is not None
        assert reloaded.lifecycle_state == "FAILED"
        assert reloaded.status == "failed"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_not_schedulable_environments_are_rejected() -> None:
    """Chapter 7.4: "No run is scheduled into `DRAINING` or `FAILED`.\""""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ExecutionEnvironmentService(engine)
        environment = await service.provision(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
        draining = await service.transition(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_id=environment.environment_id,
            target_lifecycle_state="DRAINING",
            lock_version=environment.lock_version,
        )
        with pytest.raises(DdeError) as excinfo:
            service.assert_schedulable(draining)
        assert excinfo.value.error_code == "ENVIRONMENT_FAILED"
        failed = await service.transition(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_id=draining.environment_id,
            target_lifecycle_state="FAILED",
            lock_version=draining.lock_version,
        )
        with pytest.raises(DdeError):
            service.assert_schedulable(failed)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_replace_marks_original_replacement_and_acquires_new() -> None:
    """Chapter 7.3 production mutation: FAILED → REPLACEMENT plus a new
    schedulable environment. The retired row is not schedulable."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ExecutionEnvironmentService(engine)
        environment = await service.provision(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={"cpu_seconds": 30},
            network_policy={"mode": "unenforced"},
            filesystem_policy={"workspace_root_only": True},
        )
        replaced = await service.replace(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_id=environment.environment_id,
            lock_version=environment.lock_version,
        )
        assert isinstance(replaced, ReplacedEnvironment)
        assert replaced.retired.environment_id == environment.environment_id
        assert replaced.retired.lifecycle_state == "REPLACEMENT"
        assert (
            replaced.replacement.environment.environment_id
            != environment.environment_id
        )
        assert replaced.replacement.environment.lifecycle_state == "ACTIVE"
        with pytest.raises(DdeError) as excinfo:
            service.assert_schedulable(replaced.retired)
        assert excinfo.value.error_code == "ENVIRONMENT_FAILED"
        service.assert_schedulable(replaced.replacement.environment)
        with pytest.raises(DdeError) as again:
            await service.replace(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                environment_id=replaced.retired.environment_id,
                lock_version=replaced.retired.lock_version,
            )
        assert again.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


def test_local_process_backend_provisions_real_toolchain_metadata() -> None:
    """Unit-level proof `LocalProcessBackend.provision()` reports real,
    input-dependent data (the running interpreter's own version), not a
    fabricated constant."""
    backend = LocalProcessBackend()
    handle = backend.provision(
        EnvironmentSpec(
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
    )
    assert sys.version in handle.report.toolchain_manifest["python_version"]
    assert handle.report.isolation_level == "process"
    assert handle.report.gaps  # honestly non-empty: real isolation gaps exist


@pytest.mark.asyncio
async def test_warm_pool_top_up_and_acquire_reuses_pooled_environment() -> None:
    """Chapter 7.4: a warmed pool drains on `acquire()` and only cold-
    provisions once empty. Warm hits report `reused=True` and no
    provisioning latency."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ExecutionEnvironmentService(engine)

        created = await service.top_up(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
        assert created == DEFAULT_WARM_POOL_SIZE

        first = await service.acquire(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
        assert first.reused is True
        assert first.provisioning_ms is None
        assert first.environment.lifecycle_state == "ACTIVE"

        second = await service.acquire(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
        assert second.reused is True

        third = await service.acquire(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
        assert third.reused is False
        assert third.provisioning_ms is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_release_returns_to_pool_when_workspace_destroyed() -> None:
    """Chapter 7.4 reuse gate: an ACTIVE environment whose workspace was
    destroyed and that never held credentials returns to READY (pooled) on
    `release()`, and is reused by the next `acquire()`."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ExecutionEnvironmentService(engine)

        acquired = await service.acquire(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
        assert acquired.reused is False  # cold: no pool yet

        pooled = await service.release(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_id=acquired.environment.environment_id,
            workspace_destroyed=True,
            lock_version=acquired.environment.lock_version,
        )
        assert pooled.lifecycle_state == "READY"

        reused = await service.acquire(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
        assert reused.reused is True
        assert reused.environment.environment_id == acquired.environment.environment_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_release_retires_when_workspace_not_destroyed() -> None:
    """Chapter 7.4 reuse gate: an environment whose workspace was NOT
    destroyed is never pooled — it retires immediately on `release()`."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ExecutionEnvironmentService(engine)

        acquired = await service.acquire(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
        retired = await service.release(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_id=acquired.environment.environment_id,
            workspace_destroyed=False,
            lock_version=acquired.environment.lock_version,
        )
        assert retired.lifecycle_state == "RETIRED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cross_tenant_pool_is_not_reused() -> None:
    """Chapter 3.2 / 13.9: a pooled environment is scoped to its tenant and
    project. Tenant B's `acquire()` never reuses Tenant A's warmed pool."""
    engine = new_engine()
    try:
        tenant_a = await seed_tenant(engine)
        tenant_b = await seed_tenant(engine)
        service = ExecutionEnvironmentService(engine)

        await service.top_up(
            tenant_id=tenant_a.tenant_id,
            project_id=tenant_a.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )

        acquired = await service.acquire(
            tenant_id=tenant_b.tenant_id,
            project_id=tenant_b.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
        assert acquired.reused is False
        assert acquired.environment.tenant_id == tenant_b.tenant_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_top_up_retires_stale_digest_environments() -> None:
    """Chapter 7.4 image discipline: `top_up()` retires pooled environments
    whose image digest no longer matches the current toolchain, then
    provisions fresh ones."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service_old = ExecutionEnvironmentService(
            engine, backend=_ScriptedBackend("sha256:aaaa")
        )
        service_new = ExecutionEnvironmentService(
            engine, backend=_ScriptedBackend("sha256:bbbb")
        )

        created = await service_old.top_up(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
        assert created == DEFAULT_WARM_POOL_SIZE

        created = await service_new.top_up(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
        assert created == DEFAULT_WARM_POOL_SIZE

        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            pooled = await ExecutionEnvironmentRepository().list_pooled_for_class(
                uow.connection,
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                environment_class="development",
            )
            await uow.commit()
        assert len(pooled) == DEFAULT_WARM_POOL_SIZE
        assert {env.image_digest for env in pooled} == {"sha256:bbbb"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_slow_cold_provision_emits_alert_event() -> None:
    """Chapter 7.4 economics: a cold provision exceeding the configured
    threshold emits `ExecutionEnvironmentSlowProvision` (the Chapter 16
    operational metric)."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ExecutionEnvironmentService(
            engine,
            backend=_ScriptedBackend("sha256:slow", delay_ms=50),
            cold_provision_threshold_ms=10,
        )

        acquired = await service.acquire(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            environment_class="development",
            resource_limits={},
            network_policy={},
            filesystem_policy={},
        )
        assert acquired.reused is False
        assert acquired.provisioning_ms is not None
        assert acquired.provisioning_ms >= 10

        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            events = await EventsRepository().list_events_for_aggregate(
                uow.connection,
                "execution_environment",
                acquired.environment.environment_id,
            )
            await uow.commit()
        assert any(e.event_type == "ExecutionEnvironmentSlowProvision" for e in events)
    finally:
        await engine.dispose()
