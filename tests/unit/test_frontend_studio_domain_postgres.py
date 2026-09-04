"""DDE-069 — contract, PXG and coverage against real PostgreSQL.

Proves the persistence-level guarantees the golden UI depends on:
contract versioning is publish-and-supersede, PXG revisions advance
monotonically and identify nodes stably, and a coverage snapshot knows
when it has gone stale.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from engine.contracts.frontend_contract import Obligation
from engine.core.errors import DdeError
from engine.studio.contract.service import (
    FrontendContractService,
    obligation_content_hash,
)
from engine.studio.coverage.service import CoverageService
from engine.studio.pxg.service import EdgeInput, NodeInput, PxgService
from engine.studio.reads import Availability, FrontendReadService
from tests.support.db import new_engine, seed_tenant


def _obligation(
    key: str,
    *,
    dimension: str = "screen",
    applicability: str = "REQUIRED",
    decision_ref: str | None = None,
    verification_kinds: tuple[str, ...] = (),
) -> Obligation:
    return Obligation(
        obligation_id=uuid4(),
        dimension=dimension,
        pxg_key=key,
        statement=f"{key} must exist",
        requirement_refs=[],
        applicability=applicability,
        applicability_decision_ref=decision_ref,
        verification_kinds=list(verification_kinds),
    )


@pytest.mark.asyncio
async def test_contract_publish_supersedes_and_is_idempotent() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = FrontendContractService(engine)
        scope = {
            "tenant_id": fixture.tenant_id,
            "project_id": fixture.project_id,
        }

        first = await service.publish(**scope, obligations=[_obligation("screens/a")])
        assert first.contract_version == 1
        assert first.status == "ACTIVE"

        # Republishing an identical set must not consume a version, or a
        # reconciliation loop would inflate the number forever.
        again = await service.publish(**scope, obligations=[_obligation("screens/a")])
        assert again.contract_id == first.contract_id
        assert again.contract_version == 1

        second = await service.publish(
            **scope,
            obligations=[_obligation("screens/a"), _obligation("screens/b")],
        )
        assert second.contract_version == 2
        assert second.status == "ACTIVE"

        superseded = await service.get_version(**scope, contract_version=1)
        assert superseded is not None
        assert superseded.status == "SUPERSEDED"

        active = await service.get_active(**scope)
        assert active is not None and active.contract_version == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_contract_refuses_an_unexplained_waiver() -> None:
    """The no-silent-omission rule: dropping an obligation must name the
    decision that dropped it."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = FrontendContractService(engine)
        with pytest.raises(DdeError) as excinfo:
            await service.publish(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                obligations=[
                    _obligation("screens/a", applicability="DEFERRED_APPROVED")
                ],
            )
        assert excinfo.value.error_code == "POLICY_DENIED"

        # With a decision reference the same obligation is accepted.
        published = await service.publish(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            obligations=[
                _obligation(
                    "screens/a",
                    applicability="DEFERRED_APPROVED",
                    decision_ref="EDR-1234",
                )
            ],
        )
        assert published.contract_version == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_contract_refuses_an_empty_obligation_set() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        with pytest.raises(DdeError) as excinfo:
            await FrontendContractService(engine).publish(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                obligations=[],
            )
        assert excinfo.value.error_code == "VALIDATION_FAILED"
    finally:
        await engine.dispose()


def test_content_hash_ignores_ids_and_ordering() -> None:
    left = [_obligation("screens/b"), _obligation("screens/a")]
    right = [_obligation("screens/a"), _obligation("screens/b")]
    assert obligation_content_hash(left) == obligation_content_hash(right)
    assert obligation_content_hash(left) != obligation_content_hash(
        [_obligation("screens/a")]
    )


@pytest.mark.asyncio
async def test_pxg_revisions_advance_and_keys_identify_stably() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        pxg = PxgService(engine)
        scope = {
            "tenant_id": fixture.tenant_id,
            "project_id": fixture.project_id,
        }

        assert await pxg.current_revision(**scope) == 0

        first = await pxg.apply(
            **scope,
            nodes=[
                NodeInput(pxg_key="screens/a", node_kind="screen", title="A"),
                NodeInput(
                    pxg_key="screens/a#hero",
                    node_kind="region",
                    title="Hero",
                    parent_key="screens/a",
                ),
            ],
        )
        assert first == 1

        graph = await pxg.load(**scope)
        assert graph.revision == 1
        hero = graph.node_by_key("screens/a#hero")
        assert hero is not None
        original_node_id = hero.node_id

        # Rewriting the same key updates in place: the node identity that
        # a selection, a provenance record or an inspector holds must
        # survive an edit rather than being replaced by a new row.
        second = await pxg.apply(
            **scope,
            nodes=[
                NodeInput(
                    pxg_key="screens/a#hero",
                    node_kind="region",
                    title="Hero (revised)",
                    parent_key="screens/a",
                )
            ],
        )
        assert second == 2

        graph = await pxg.load(**scope)
        hero = graph.node_by_key("screens/a#hero")
        assert hero is not None
        assert hero.node_id == original_node_id
        assert hero.title == "Hero (revised)"
        assert hero.lock_version == 2
        assert graph.revision == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pxg_refuses_malformed_keys_and_empty_writes() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        pxg = PxgService(engine)
        scope = {
            "tenant_id": fixture.tenant_id,
            "project_id": fixture.project_id,
        }

        for hostile in ("../escape", "has space", "", "#leading"):
            with pytest.raises(DdeError) as excinfo:
                await pxg.apply(
                    **scope,
                    nodes=[NodeInput(pxg_key=hostile, node_kind="screen", title="x")],
                )
            assert excinfo.value.error_code == "VALIDATION_FAILED", hostile

        with pytest.raises(DdeError):
            await pxg.apply(**scope)

        with pytest.raises(DdeError):
            await pxg.apply(
                **scope,
                nodes=[
                    NodeInput(
                        pxg_key="screens/a",
                        node_kind="screen",
                        title="A",
                        parent_key="screens/a",
                    )
                ],
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_dangling_edges_and_orphans_surface_rather_than_crash() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        pxg = PxgService(engine)
        scope = {
            "tenant_id": fixture.tenant_id,
            "project_id": fixture.project_id,
        }
        await pxg.apply(
            **scope,
            nodes=[
                NodeInput(pxg_key="screens/a", node_kind="screen", title="A"),
                NodeInput(
                    pxg_key="screens/b",
                    node_kind="screen",
                    title="B",
                    parent_key="journeys/ghost",
                ),
            ],
            edges=[
                EdgeInput(
                    from_key="screens/a",
                    to_key="screens/nowhere",
                    edge_kind="navigates_to",
                )
            ],
        )
        graph = await pxg.load(**scope)
        assert [item.to_key for item in graph.dangling_edges()] == ["screens/nowhere"]
        assert [item.pxg_key for item in graph.orphan_nodes()] == ["screens/b"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_coverage_snapshot_goes_stale_when_the_graph_moves() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        scope = {
            "tenant_id": fixture.tenant_id,
            "project_id": fixture.project_id,
        }
        contracts = FrontendContractService(engine)
        pxg = PxgService(engine)
        coverage = CoverageService(engine)

        await contracts.publish(
            **scope,
            obligations=[
                _obligation("screens/a"),
                _obligation("screens/b"),
            ],
        )
        await pxg.apply(
            **scope,
            nodes=[
                NodeInput(pxg_key="screens/a", node_kind="screen", title="A"),
                NodeInput(
                    pxg_key="screens/a#hero",
                    node_kind="region",
                    title="Hero",
                    parent_key="screens/a",
                ),
            ],
        )

        snapshot = await coverage.recompute(**scope)
        assert snapshot.pxg_revision == 1
        assert snapshot.summary_state == "ASSESSED"
        assert snapshot.weighted_percent == 50.0

        read = await coverage.latest(**scope)
        assert read.stale is False
        assert read.snapshot is not None

        # Moving the graph forward must not leave the old number looking
        # current.
        await pxg.apply(
            **scope,
            nodes=[NodeInput(pxg_key="screens/b", node_kind="screen", title="B")],
        )
        read = await coverage.latest(**scope)
        assert read.stale is True
        assert read.current_pxg_revision == 2

        recomputed = await coverage.recompute(**scope)
        assert recomputed.pxg_revision == 2
        assert recomputed.weighted_percent == 100.0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_coverage_without_a_contract_is_unassessable_not_zero() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        with pytest.raises(DdeError) as excinfo:
            await CoverageService(engine).recompute(
                tenant_id=fixture.tenant_id, project_id=fixture.project_id
            )
        assert excinfo.value.error_code == "CONTEXT_INCOMPLETE"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_read_projection_reports_unknown_rather_than_zero() -> None:
    """The counts a golden explorer group cannot yet source must arrive
    as UNKNOWN, never as a plausible zero."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        scope = {
            "tenant_id": fixture.tenant_id,
            "project_id": fixture.project_id,
        }
        await PxgService(engine).apply(
            **scope,
            nodes=[
                NodeInput(pxg_key="screens/a", node_kind="screen", title="A"),
                NodeInput(
                    pxg_key="journeys/checkout",
                    node_kind="journey",
                    title="Checkout",
                ),
            ],
        )
        snapshot = await FrontendReadService(engine).snapshot(**scope)

        groups = {group.key: group for group in snapshot.explorer.groups}
        assert groups["screens"].count.value == 1
        assert groups["journeys"].count.value == 1
        assert groups["components"].count.value == 0
        assert groups["components"].count.availability is Availability.EMPTY

        for key in ("sources", "templates", "locks"):
            count = groups[key].count
            assert count.known is False, key
            assert count.value is None, key
            assert count.availability is Availability.NOT_IMPLEMENTED, key
            assert count.reason

        # No coverage has been computed, so the ring has no number.
        assert snapshot.coverage.weighted_percent is None
        assert snapshot.coverage.availability is Availability.NOT_CONFIGURED

        # Serving identity is never claimed without evidence.
        manager = next(
            role for role in snapshot.orchestrator.roles if role.role == "manager_chair"
        )
        assert manager.serving is None
        assert manager.serving_confidence == "UNATTESTED"
        assert snapshot.orchestrator.availability is Availability.NOT_IMPLEMENTED
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stale_coverage_is_not_rendered_as_a_current_percentage() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        scope = {
            "tenant_id": fixture.tenant_id,
            "project_id": fixture.project_id,
        }
        await FrontendContractService(engine).publish(
            **scope, obligations=[_obligation("screens/a")]
        )
        pxg = PxgService(engine)
        await pxg.apply(
            **scope,
            nodes=[
                NodeInput(pxg_key="screens/a", node_kind="screen", title="A"),
                NodeInput(
                    pxg_key="screens/a#hero",
                    node_kind="region",
                    title="Hero",
                    parent_key="screens/a",
                ),
            ],
        )
        await CoverageService(engine).recompute(**scope)
        await pxg.apply(
            **scope,
            nodes=[NodeInput(pxg_key="screens/z", node_kind="screen", title="Z")],
        )

        snapshot = await FrontendReadService(engine).snapshot(**scope)
        assert snapshot.coverage.stale is True
        assert snapshot.coverage.weighted_percent is None
        assert snapshot.coverage.availability is Availability.DEGRADED
        assert "revision" in (snapshot.coverage.reason or "")
        assert any(
            item.category == "coverage_stale" for item in snapshot.attention.items
        )
    finally:
        await engine.dispose()
