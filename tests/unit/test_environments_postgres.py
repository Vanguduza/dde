"""PostgreSQL-backed `engine.environments`: schema, state-transition and
negative tests (Chapter 19.1). Exercises `engine.environments.service.
ExecutionEnvironmentService`, the production writer of
`execution_environments` (Chapter 3.8), against a real database and the
real `LocalProcessBackend` (Chapter 7.3 `type = "local"`)."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

import pytest

from engine.core.errors import DdeError
from engine.environments.backends.base import EnvironmentSpec, ProvisionedEnvironment
from engine.environments.backends.local_process import LocalProcessBackend
from engine.environments.repository import ExecutionEnvironmentRepository
from engine.environments.service import ExecutionEnvironmentService
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
