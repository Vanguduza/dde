"""Chapter 11.6 ProductEnvironment lifecycle against real PostgreSQL
(migration 0012).

Production mutation call sites under test:
- `ProductEnvironmentService.provision` -- creates the row in
  PROVISIONING, refuses worker-originated production requests (typed
  FORBIDDEN, Chapter 15.5) and requires a TTL for ephemeral previews;
  idempotent on the caller's idempotency key;
- `ProductEnvironmentService.apply_migrations_forward` -- Chapter 11.6's
  bidirectional migration verification: forward-apply against an empty
  throwaway database AND forward-apply against a snapshot of the previous
  release's schema; a migration verified only on empty stays un-READY;
- `ProductEnvironmentService.seed` -- applies a versioned, content-hashed
  SeedDataset and proves reproducibility (same dataset id + hash twice =>
  identical observable state);
- `ProductEnvironmentService.mark_in_use` / `teardown` /
  `record_failure` / `teardown_expired` -- the rest of the transition
  table, TTL expiry sweep with an abandoned-preview event on the existing
  EventService, failure snapshots as evidence-artifact references.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from engine.core.errors import DdeError
from engine.product_env.service import (
    HUMAN_ORIGIN,
    WORKER_ORIGIN,
    ProductEnvironmentService,
)
from engine.truth.db import open_unit_of_work
from tests.support.db import new_engine, seed_tenant


def _now() -> datetime:
    return datetime.now(UTC)


def _provision_kwargs(tenant, **overrides):
    kwargs = {
        "tenant_id": tenant.tenant_id,
        "project_id": tenant.project_id,
        "env_class": "ephemeral_preview",
        "source_revision": "abc1234",
        "build_artifact_ref": "r2://artifacts/build.tar.gz",
        "runtime_topology_ref": {"compose": "docker-compose.yml"},
        "datastore_ref": "postgres://throwaway/db",
        "requested_by_origin": HUMAN_ORIGIN,
        "ttl_seconds": 3600,
    }
    kwargs.update(overrides)
    return kwargs


async def _status_of(engine, tenant, product_env_id: str) -> str:
    async with open_unit_of_work(
        engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
    ) as uow:
        row = (
            await uow.connection.execute(
                text(
                    "SELECT status FROM product_environments "
                    "WHERE product_env_id = :pid"
                ),
                {"pid": product_env_id},
            )
        ).one()
        await uow.commit()
    return str(row[0])


@pytest.mark.asyncio
async def test_provision_happy_path_creates_provisioning_row_with_ttl() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ProductEnvironmentService(engine)

        record = await service.provision(**_provision_kwargs(tenant))

        assert record.status == "PROVISIONING"
        assert record.ttl_expires_at is not None
        fetched = await service.get_product_environment(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            product_env_id=record.product_env_id,
        )
        assert fetched.product_env_id == record.product_env_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_provision_is_idempotent_on_the_same_key() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ProductEnvironmentService(engine)

        first = await service.provision(
            **_provision_kwargs(tenant), idempotency_key="pe:key-1"
        )
        second = await service.provision(
            **_provision_kwargs(tenant), idempotency_key="pe:key-1"
        )

        assert second.product_env_id == first.product_env_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_originated_production_request_is_refused_at_call_site() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ProductEnvironmentService(engine)

        with pytest.raises(DdeError) as error:
            await service.provision(
                **_provision_kwargs(
                    tenant, env_class="production", requested_by_origin=WORKER_ORIGIN
                ),
                idempotency_key="pe:worker-prod",
            )
        assert error.value.error_code == "FORBIDDEN"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_originated_staging_is_also_refused() -> None:
    """The rule is about production-class environments; staging is
    production-class for provisioning purposes in this service."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ProductEnvironmentService(engine)
        with pytest.raises(DdeError) as error:
            await service.provision(
                **_provision_kwargs(
                    tenant, env_class="staging", requested_by_origin=WORKER_ORIGIN
                ),
                idempotency_key="pe:worker-staging",
            )
        assert error.value.error_code == "FORBIDDEN"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_ephemeral_preview_without_ttl_is_refused() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ProductEnvironmentService(engine)
        with pytest.raises(DdeError) as error:
            await service.provision(
                **_provision_kwargs(tenant, ttl_seconds=None),
                idempotency_key="pe:no-ttl",
            )
        assert error.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_full_lifecycle_walks_the_transition_table() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ProductEnvironmentService(engine)
        record = await service.provision(**_provision_kwargs(tenant))

        migrated = await service.apply_migrations_forward(
            record, empty_verified=True, previous_verified=True
        )
        assert migrated.status == "MIGRATING"

        seeded = await service.seed(
            migrated,
            slug="erp-baseline",
            content_hash="deadbeef",
            artifact_ref="r2://seeds/erp-baseline-v1.sql",
            created_by="principal-1",
        )
        assert seeded.status == "SEEDING"

        ready = await service.mark_ready(seeded)
        assert ready.status == "READY"
        assert ready.base_url is not None
        in_use = await service.mark_in_use(
            ready, mission_id=None, verification_run_ref="vr-1"
        )
        assert in_use.status == "IN_USE"

        torn_down = await service.teardown(in_use)
        assert torn_down.status == "TEARDOWN"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seed_twice_from_same_dataset_yields_identical_state() -> None:
    """Reproducibility: same dataset identity + hash => byte-identical
    observable state of the datastore after each seeding."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ProductEnvironmentService(engine)
        record = await service.provision(**_provision_kwargs(tenant))
        migrated = await service.apply_migrations_forward(
            record, empty_verified=True, previous_verified=True
        )

        first = await service.seed(
            migrated,
            slug="erp-baseline",
            content_hash="cafe1234",
            artifact_ref="r2://seeds/erp-baseline-v1.sql",
            created_by="principal-1",
        )
        first_state = await service.observable_state_fingerprint(first)
        torn = await service.record_failure(
            first,
            reason="invariant failure — reproducible from dataset",
            snapshot_ref="r2://snapshots/inv.tar.gz",
        )
        second_record = await service.provision(**_provision_kwargs(tenant))
        second_migrated = await service.apply_migrations_forward(
            second_record, empty_verified=True, previous_verified=True
        )
        second = await service.seed(
            second_migrated,
            slug="erp-baseline",
            content_hash="cafe1234",
            artifact_ref="r2://seeds/erp-baseline-v1.sql",
            created_by="principal-1",
        )
        second_state = await service.observable_state_fingerprint(second)

        assert first_state == second_state
        assert second.seed_dataset_id == first.seed_dataset_id
        await service.teardown(torn)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_migration_verification_is_bidirectional_or_not_ready() -> None:
    """A migration verified only on an empty database must never reach
    READY — forward_previous is mandatory (Chapter 11.6)."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ProductEnvironmentService(engine)
        record = await service.provision(**_provision_kwargs(tenant))
        migrated = await service.apply_migrations_forward(record)

        # Only the empty-database half verified so far.
        assert migrated.migration_verification is not None
        assert migrated.migration_verification.forward_empty["verified"] is True
        assert migrated.migration_verification.forward_previous["verified"] is False
        with pytest.raises(DdeError) as error:
            await service.mark_ready(migrated)
        assert error.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_illegal_transition_refused_and_row_unchanged() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ProductEnvironmentService(engine)
        record = await service.provision(**_provision_kwargs(tenant))

        with pytest.raises(DdeError):
            await service.mark_ready(record)  # PROVISIONING -> READY skips two states

        assert await _status_of(engine, tenant, str(record.product_env_id)) == (
            "PROVISIONING"
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_failure_mid_lifecycle_records_snapshot_and_allows_teardown() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ProductEnvironmentService(engine)
        record = await service.provision(**_provision_kwargs(tenant))

        failed = await service.record_failure(
            record,
            reason="migration driver crashed mid-forward",
            snapshot_ref="r2://snapshots/pe-crash.tar.gz",
            snapshot_bytes=b"snapshot-bytes",
        )
        assert failed.status == "FAILED"
        assert failed.failure_snapshot is not None
        assert failed.failure_snapshot.content_hash
        torn_down = await service.teardown(failed)
        assert torn_down.status == "TEARDOWN"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_teardown_expired_destroys_only_expired_previews() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ProductEnvironmentService(engine)
        now = _now()

        expired = await service.provision(
            **_provision_kwargs(tenant, ttl_seconds=-60),
            idempotency_key="pe:expired",
        )
        alive = await service.provision(
            **_provision_kwargs(tenant, ttl_seconds=3600),
            idempotency_key="pe:alive",
        )

        swept = await service.teardown_expired(now=now)
        swept_ids = {str(row.product_env_id) for row in swept}
        assert str(expired.product_env_id) in swept_ids
        assert str(alive.product_env_id) not in swept_ids

        assert (
            await _status_of(engine, tenant, str(expired.product_env_id)) == "TEARDOWN"
        )
        assert (
            await _status_of(engine, tenant, str(alive.product_env_id))
            == "PROVISIONING"
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_abandoned_preview_expiry_emits_observable_event() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ProductEnvironmentService(engine)
        expired = await service.provision(
            **_provision_kwargs(tenant, ttl_seconds=-1),
            idempotency_key="pe:event",
        )
        await service.teardown_expired(now=_now())

        async with open_unit_of_work(
            engine, tenant_id=tenant.tenant_id, project_id=tenant.project_id
        ) as uow:
            rows = (
                await uow.connection.execute(
                    text(
                        "SELECT event_type FROM events WHERE aggregate_type = "
                        "'product_environment' AND aggregate_id = :aid"
                    ),
                    {"aid": str(expired.product_env_id)},
                )
            ).all()
            await uow.commit()
        types = {row[0] for row in rows}
        assert "ProductEnvironmentAbandoned" in types
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_production_rows_never_carry_execution_reachability() -> None:
    """Chapter 11.6: production environments are never reachable from an
    ExecutionEnvironment. The service refuses to bind one at the only
    write path that could create such a link (credentials/topology
    binding at provision time)."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = ProductEnvironmentService(engine)
        with pytest.raises(DdeError) as error:
            await service.provision(
                **_provision_kwargs(
                    tenant,
                    env_class="production",
                    execution_environment_binding="ee-1234",
                ),
                idempotency_key="pe:prod-ee-binding",
            )
        assert error.value.error_code == "FORBIDDEN"
    finally:
        await engine.dispose()
