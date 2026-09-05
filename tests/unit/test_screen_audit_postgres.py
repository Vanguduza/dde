"""PostgreSQL proof for DDE-069 Screen Audit persistence/incremental lifecycle."""

from __future__ import annotations

from uuid import uuid4

import pytest

from engine.contracts.frontend_contract import Obligation
from engine.contracts.pxg_node import SourceRef
from engine.core.errors import DdeError
from engine.studio.audit.reads import ScreenAuditReadService
from engine.studio.audit.service import ScreenAuditService
from engine.studio.contract.service import FrontendContractService
from engine.studio.pxg.service import NodeInput, PxgService
from tests.support.db import new_engine, seed_tenant


@pytest.mark.asyncio
async def test_screen_audit_full_incremental_and_exception_lifecycle() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        pxg = PxgService(engine)
        contracts = FrontendContractService(engine)
        audit = ScreenAuditService(engine, pxg=pxg, contracts=contracts)
        reads = ScreenAuditReadService(engine)
        await pxg.apply(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            nodes=[
                NodeInput(
                    pxg_key="screens/checkout",
                    node_kind="screen",
                    title="Checkout",
                    source_refs=(SourceRef(path="src/Checkout.tsx"),),
                    attributes={
                        "route": "/checkout",
                        "bound_verification_kinds": ["silhouette", "visual_critique"],
                    },
                )
            ],
        )
        await contracts.publish(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            obligations=[
                Obligation(
                    obligation_id=uuid4(),
                    dimension="screen",
                    pxg_key="screens/checkout",
                    statement="Checkout must exist",
                    requirement_refs=["ORDER-F023"],
                    applicability="REQUIRED",
                    verification_kinds=[],
                ),
                Obligation(
                    obligation_id=uuid4(),
                    dimension="state",
                    pxg_key="screens/checkout#error",
                    statement="Checkout must expose payment failure",
                    requirement_refs=["ORDER-F023"],
                    applicability="REQUIRED",
                    verification_kinds=[],
                ),
            ],
        )

        first = await audit.run(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=None,
            trigger="FULL",
        )
        assert first.run.status == "COMPLETED"
        matrix = await reads.matrix(
            tenant_id=fixture.tenant_id, project_id=fixture.project_id
        )
        finding_types = {item.finding_type for item in matrix.findings}
        assert "REQUIRED_STATE_MISSING" in finding_types
        assert "REQUIRED_SCREEN_VERIFICATION_NOT_CURRENT" in finding_types
        assert matrix.summary.currentness == "CURRENT"

        visual = next(
            item
            for item in matrix.findings
            if item.finding_type == "REQUIRED_SCREEN_VERIFICATION_NOT_CURRENT"
        )
        with pytest.raises(DdeError, match="decision"):
            await audit.accept_exception(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                finding_id=visual.finding_id,
                decision_ref="",
                principal_id=fixture.principal_id,
            )
        accepted = await audit.accept_exception(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            finding_id=visual.finding_id,
            decision_ref="EDR-AUDIT-EXCEPTION-1",
            principal_id=fixture.principal_id,
        )
        assert accepted.status == "ACCEPTED_EXCEPTION"
        assert accepted.resolution_ref is not None

        await pxg.apply(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            nodes=[
                NodeInput(
                    pxg_key="screens/checkout#error",
                    node_kind="state",
                    title="Payment error",
                    parent_key="screens/checkout",
                    attributes={"state_name": "error"},
                )
            ],
        )
        await audit.invalidate_affected(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            affected_keys=("screens/checkout#error",),
        )
        stale = await reads.summary(
            tenant_id=fixture.tenant_id, project_id=fixture.project_id
        )
        assert stale.currentness == "STALE"
        second = await audit.run(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=None,
            trigger="INCREMENTAL",
            affected_keys=("screens/checkout#error",),
        )
        assert "screens/checkout" in second.run.affected_keys
        current = await reads.matrix(
            tenant_id=fixture.tenant_id, project_id=fixture.project_id
        )
        assert current.summary.currentness == "CURRENT"
        assert not any(
            item.finding_type == "REQUIRED_STATE_MISSING" for item in current.findings
        )
        screen = next(
            item for item in current.screens if item.pxg_key == "screens/checkout"
        )
        assert screen.dimension_states["STATE"] == "PASS"
    finally:
        await engine.dispose()
