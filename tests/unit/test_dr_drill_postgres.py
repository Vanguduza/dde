"""Chapter 17.5 WORM + control-plane drill at production call sites."""

from __future__ import annotations

from uuid import uuid4

import pytest

from engine.audit.service import AuditService
from engine.core.errors import DdeError
from engine.dr.drill import ControlPlaneDrill
from engine.dr.worm import WormRetentionService
from tests.support.db import new_engine, seed_tenant


@pytest.mark.asyncio
async def test_purge_evidence_refuses_even_when_row_is_unknown() -> None:
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        with pytest.raises(DdeError) as excinfo:
            await WormRetentionService(engine).purge_evidence(
                tenant_id=tenant.tenant_id,
                project_id=tenant.project_id,
                evidence_id=uuid4(),
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
        assert excinfo.value.details is not None
        assert excinfo.value.details["control"] == "worm_retention"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_control_plane_drill_restores_into_isolated_database() -> None:
    """Production caller: verify_chain, WORM refuse, restore, emergency_revoke."""
    engine = new_engine()
    try:
        tenant = await seed_tenant(engine)
        await AuditService(engine).append(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
            event_type="drill.seed",
            payload={"mission": "DDE-062"},
        )
        result = await ControlPlaneDrill(engine).run(
            tenant_id=tenant.tenant_id,
            project_id=tenant.project_id,
        )
        assert result.chain_verified is True
        assert result.worm_held is True
        assert result.object_worm_held is True
        assert result.restore.chain_verified is True
        assert result.restore.audit_events_restored >= 2
        assert result.emergency_revoke_count == 0
        assert result.restore.pitr.archive_mode in {"off", "on", "always"}
    finally:
        await engine.dispose()
