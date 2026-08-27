"""DDE-064 ReadinessReview production caller (audit mutation, Ch.18.6)."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from engine.readiness.removal import KEEP, RemovalMeasurement
from engine.readiness.review import ReadinessReview
from tests.support.db import new_engine, seed_tenant


@pytest.mark.asyncio
async def test_readiness_review_fail_closes_to_keep_and_audits() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        result = await ReadinessReview(engine).run(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
        )
        assert result.inventory_complete is True
        assert result.proposed_edrs == ()
        assert all(v.decision == KEEP for v in result.verdicts)
        assert all(v.reason == "unmeasured" for v in result.verdicts)
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT event_type FROM audit_events "
                        "WHERE tenant_id = :tenant_id AND event_type = "
                        "'readiness.reviewed'"
                    ),
                    {"tenant_id": tenant.tenant_id},
                )
            ).all()
        assert len(rows) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_readiness_review_proposes_edr_without_deleting() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        justifying = RemovalMeasurement(
            verified_success_now=4,
            overhead_tokens_now=800,
            verified_success_if_removed=4,
            overhead_tokens_if_removed=400,
        )
        result = await ReadinessReview(engine).run(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            measurements={"context_critic": justifying},
        )
        assert result.proposed_edrs == ("context_critic",)
        from pathlib import Path

        from engine.readiness.inventory import REMOVAL_CANDIDATES

        root = Path(__file__).resolve().parents[2]
        assert (root / REMOVAL_CANDIDATES["context_critic"]).is_file()
    finally:
        await engine.dispose()
