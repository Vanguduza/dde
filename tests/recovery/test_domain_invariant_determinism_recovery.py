"""Chapter 11.5 recovery-style proof: invariant evaluation is
deterministic and idempotent at its production mutation site.

The Chapter 12.4 rule for this surface: an evaluation is a READ over a
real datastore plus one append-only recorded outcome. Re-running the same
evaluation (same definition_version, same environment, same idempotency
key) must never append a second row, must never flip the verdict, and —
after a FAILED evaluation is recorded and the underlying rows are then
repaired by a real repair task — a NEW evaluation under a NEW key records
the repaired state as PASSED without touching the first row's history.
A failed evaluation is never blind-retried into green under the same key:
the ledger refuses re-execution of a completed command with different
inputs, and replay returns the stored outcome.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from engine.invariants.service import DomainInvariantService
from tests.recovery.support_helpers import (
    plant_duplicate_requirements,
    ready_environment,
    repair_requirements,
)
from tests.support.db import new_engine, seed_tenant


@pytest.mark.asyncio
async def test_failed_then_repaired_records_pass_without_history_rewrite() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        service = DomainInvariantService(engine)
        record = await service.define(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            name="requirement_statement_unique",
            description="Requirement statements are unique within a project",
            predicate={
                "kind": "unique_columns",
                "table_ref": "public.requirements",
                "columns": ["project_id", "statement"],
            },
            financial_state=False,
            required_fixture_class="erp-baseline",
            product_env_class="ephemeral_preview",
            created_by="principal-1",
        )
        env = await ready_environment(engine, tenant)

        statement = f"dup-stmt-{uuid4().hex[:8]}"
        await plant_duplicate_requirements(engine, tenant, statement=statement)

        datastore_url = str(engine.url.render_as_string(hide_password=False))

        failed = await service.evaluate(
            record,
            product_env=env,
            datastore_url=datastore_url,
            idempotency_key=f"inv-eval-fail:{env.product_env_id}",
        )
        assert failed.status == "FAILED"

        # The repair task does its real work on the real rows.
        await repair_requirements(engine, tenant, statement=statement)

        repaired = await service.evaluate(
            record,
            product_env=env,
            datastore_url=datastore_url,
            idempotency_key=f"inv-eval-repaired:{env.product_env_id}",
        )

        assert repaired.status == "PASSED"
        assert repaired.evaluation_id != failed.evaluation_id

        # The first (FAILED) outcome is history: replaying the original key
        # returns the original FAILED row, never the newer PASS.
        replay = await service.evaluate(
            record,
            product_env=env,
            datastore_url=datastore_url,
            idempotency_key=f"inv-eval-fail:{env.product_env_id}",
        )
        assert replay.evaluation_id == failed.evaluation_id
        assert replay.status == "FAILED"
    finally:
        await engine.dispose()
