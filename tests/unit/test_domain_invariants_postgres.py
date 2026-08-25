"""Chapter 11.5 domain invariant engine against real PostgreSQL
(migration 0013).

Production mutation call sites under test:
- `DomainInvariantService.define` -- registers a named, versioned,
  content-hashed invariant definition; re-defining the same definition is
  idempotent on `definition_version` (Chapter 3.10: no duplicate mint);
- `DomainInvariantService.retire` -- the single lifecycle mutation, typed
  refusal on an already-retired definition, row left untouched;
- `DomainInvariantService.evaluate` -- evaluates a definition's compiled
  predicate against the REAL rows of a REAL ProductEnvironment datastore
  and records one append-only `InvariantEvaluation`; guarded by the
  Chapter 12.5 command ledger so a repeated call with the same key
  returns the first recorded outcome without re-executing (deterministic,
  idempotent evaluation); refuses environments that are not READY/IN_USE
  and class mismatches between definition and environment.

The planted-failure tests seed real duplicate rows through the same RLS
path production writes go through, then break the declared uniqueness
condition, and pin FAILED with concrete violations -- never fabricated
from absence of data.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.core.errors import DdeError
from engine.invariants.service import DomainInvariantService
from engine.product_env.service import HUMAN_ORIGIN, ProductEnvironmentService
from tests.recovery.support_helpers import (
    plant_duplicate_requirements,
    purge_planted_requirements,
)
from tests.support.db import new_engine, seed_tenant


def _unique_invariant_kwargs(tenant, **overrides):
    kwargs = {
        "tenant_id": tenant.tenant_id,
        "project_id": tenant.project_id,
        "name": "requirement_statement_unique",
        "description": "Requirement statements are unique within a project",
        "predicate": {
            "kind": "unique_columns",
            "table_ref": "public.requirements",
            "columns": ["project_id", "statement"],
        },
        "financial_state": False,
        "required_fixture_class": "erp-baseline",
        "product_env_class": "ephemeral_preview",
        "created_by": "principal-1",
    }
    kwargs.update(overrides)
    return kwargs


async def _ready_environment(engine: AsyncEngine, tenant) -> object:
    """A READY ephemeral_preview whose datastore is this test database."""
    product_envs = ProductEnvironmentService(engine)
    record = await product_envs.provision(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        env_class="ephemeral_preview",
        source_revision="abc1234",
        build_artifact_ref="r2://artifacts/build.tar.gz",
        runtime_topology_ref={"compose": "docker-compose.yml"},
        datastore_ref="throwaway",
        requested_by_origin=HUMAN_ORIGIN,
        ttl_seconds=3600,
    )
    migrated = await product_envs.apply_migrations_forward(
        record, empty_verified=True, previous_verified=True
    )
    seeded = await product_envs.seed(
        migrated,
        slug="erp-baseline",
        content_hash="cafe1234",
        artifact_ref="r2://seeds/erp-baseline-v1.sql",
        created_by="principal-1",
    )
    return await product_envs.mark_ready(seeded)


async def _ready_environment(engine: AsyncEngine, tenant) -> object:
    """A READY ephemeral_preview whose datastore is this test database."""
    product_envs = ProductEnvironmentService(engine)
    record = await product_envs.provision(
        tenant_id=tenant.tenant_id,
        project_id=tenant.project_id,
        env_class="ephemeral_preview",
        source_revision="abc1234",
        build_artifact_ref="r2://artifacts/build.tar.gz",
        runtime_topology_ref={"compose": "docker-compose.yml"},
        datastore_ref="throwaway",
        requested_by_origin=HUMAN_ORIGIN,
        ttl_seconds=3600,
    )
    migrated = await product_envs.apply_migrations_forward(
        record, empty_verified=True, previous_verified=True
    )
    seeded = await product_envs.seed(
        migrated,
        slug="erp-baseline",
        content_hash="cafe1234",
        artifact_ref="r2://seeds/erp-baseline-v1.sql",
        created_by="principal-1",
    )
    return await product_envs.mark_ready(seeded)


@pytest.mark.asyncio
async def test_define_is_versioned_and_idempotent_on_definition_hash() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = DomainInvariantService(engine)

        first = await service.define(**_unique_invariant_kwargs(tenant))
        second = await service.define(**_unique_invariant_kwargs(tenant))

        assert first.definition_version == second.definition_version
        assert first.invariant_id == second.invariant_id
        assert first.status == "ACTIVE"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_material_change_creates_a_new_version_not_an_overwrite() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = DomainInvariantService(engine)

        original = await service.define(**_unique_invariant_kwargs(tenant))
        changed = await service.define(
            **_unique_invariant_kwargs(tenant, description="tighter wording")
        )

        assert changed.definition_version != original.definition_version
        assert changed.invariant_id != original.invariant_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_retire_is_the_only_lifecycle_mutation_and_is_typed() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = DomainInvariantService(engine)
        record = await service.define(**_unique_invariant_kwargs(tenant))

        retired = await service.retire(record)
        assert retired.status == "RETIRED"

        with pytest.raises(DdeError) as error:
            await service.retire(retired)
        assert error.value.error_code == "VERSION_CONFLICT"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_evaluate_records_pass_over_clean_real_rows() -> None:
    engine = new_engine()
    try:
        # Shared-dev-DB hygiene: planted dup rows from an interrupted
        # earlier suite must not leak into a "clean" evaluation.
        await purge_planted_requirements(engine)
        tenant = await seed_tenant(engine)
        service = DomainInvariantService(engine)
        record = await service.define(**_unique_invariant_kwargs(tenant))
        env = await _ready_environment(engine, tenant)

        evaluation = await service.evaluate(
            record,
            product_env=env,
            datastore_url=str(engine.url.render_as_string(hide_password=False)),
            idempotency_key=f"inv-eval:{record.definition_version}:{env.product_env_id}",
        )

        assert evaluation.status == "PASSED"
        assert evaluation.violations == []
        assert isinstance(evaluation.rows_checked, int) or (
            evaluation.rows_checked >= 0
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_same_key_replay_returns_identical_recorded_outcome() -> None:
    """Chapter 12.5 / mission brief: re-running an invariant evaluation
    with the same inputs yields the SAME recorded outcome — the ledger
    replays the first row instead of appending a twin."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = DomainInvariantService(engine)
        record = await service.define(**_unique_invariant_kwargs(tenant))
        env = await _ready_environment(engine, tenant)
        key = f"inv-eval:{record.definition_version}:{env.product_env_id}"

        first = await service.evaluate(
            record,
            product_env=env,
            datastore_url=str(engine.url.render_as_string(hide_password=False)),
            idempotency_key=key,
        )
        second = await service.evaluate(
            record,
            product_env=env,
            datastore_url=str(engine.url.render_as_string(hide_password=False)),
            idempotency_key=key,
        )

        assert second.evaluation_id == first.evaluation_id
        assert second.status == first.status
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_planted_duplicate_rows_fail_with_real_violations() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = DomainInvariantService(engine)
        record = await service.define(**_unique_invariant_kwargs(tenant))

        # The project's own seeded requirements do not violate anything;
        # the duplicates are what trip the predicate.
        await plant_duplicate_requirements(
            engine, tenant, statement=f"dup-stmt-{uuid4().hex[:8]}"
        )

        env = await _ready_environment(engine, tenant)
        evaluation = await service.evaluate(
            record,
            product_env=env,
            datastore_url=str(engine.url.render_as_string(hide_password=False)),
            idempotency_key=f"inv-eval-dup:{env.product_env_id}",
        )

        assert evaluation.status == "FAILED"
        assert len(evaluation.violations) == 1
        assert evaluation.violations[0].kind == "duplicate_group"
        assert str(tenant.project_id) in evaluation.violations[0].detail
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_evaluation_refuses_environment_not_ready() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = DomainInvariantService(engine)
        record = await service.define(**_unique_invariant_kwargs(tenant))
        product_envs = ProductEnvironmentService(engine)
        provisioning = await product_envs.provision(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            env_class="ephemeral_preview",
            source_revision="abc1234",
            build_artifact_ref="r2://artifacts/build.tar.gz",
            runtime_topology_ref={"compose": "docker-compose.yml"},
            datastore_ref="postgres://throwaway/db",
            requested_by_origin=HUMAN_ORIGIN,
            ttl_seconds=3600,
        )

        with pytest.raises(DdeError) as error:
            await service.evaluate(
                record,
                product_env=provisioning,
                datastore_url="postgresql+asyncpg://x/y",
                idempotency_key="inv-eval-not-ready",
            )
        assert error.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_evaluation_refuses_product_env_class_mismatch() -> None:
    """Chapter 11.5: each invariant declares the ProductEnvironment class
    it must run in; evaluating against any other class is refused at the
    mutation site, not silently tolerated."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = DomainInvariantService(engine)
        await service.define(**_unique_invariant_kwargs(tenant))
        env = await _ready_environment(engine, tenant)

        changed = await service.define(
            **_unique_invariant_kwargs(tenant, product_env_class="production")
        )
        with pytest.raises(DdeError) as error:
            await service.evaluate(
                changed,
                product_env=env,
                datastore_url=str(engine.url.render_as_string(hide_password=False)),
                idempotency_key="inv-eval-mismatch",
            )
        assert error.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_financial_failure_carries_human_visibility_marker() -> None:
    """Chapter 11.5: a failing financial-state invariant records the
    financial_state marker on the row itself and keeps the named repair
    task slot unassigned-but-present — the failure is visible to a human
    workflow, never auto-repaired."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = DomainInvariantService(engine)
        financial = await service.define(
            **_unique_invariant_kwargs(tenant, financial_state=True)
        )

        await plant_duplicate_requirements(
            engine, tenant, statement=f"fin-stmt-{uuid4().hex[:8]}"
        )
        env = await _ready_environment(engine, tenant)
        evaluation = await service.evaluate(
            financial,
            product_env=env,
            datastore_url=str(engine.url.render_as_string(hide_password=False)),
            idempotency_key=f"inv-eval-fin:{env.product_env_id}",
        )

        assert evaluation.status == "FAILED"
        assert evaluation.financial_state is True
        assert evaluation.repair_task_ref is None
        assert isinstance(evaluation.invariant_id, UUID)
    finally:
        await engine.dispose()
