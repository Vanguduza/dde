"""EDR-0019 Epic C discovery runtime against real PostgreSQL.

These prove the behaviour the contracts only declare: that independent sightings
merge, that history is append-only and dense, that an illegal transition is
refused, and above all that a passing sandbox trial advances lifecycle without
ever raising source trust.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from engine.core.errors import DdeError
from engine.source.discovery.repository import DiscoveryRepository
from engine.source.discovery.service import DiscoveryService
from engine.source.discovery.tables import (
    discovery_candidates,
    graph_trust_projections,
)
from engine.truth.db import open_unit_of_work
from tests.support.db import (
    ensure_rls_probe_role,
    new_engine,
    open_rls_probe,
    seed_tenant,
)

pytestmark = pytest.mark.asyncio

ZIE = "https://github.com/Zie619/n8n-workflows"


async def _service_and_tenant():
    engine = new_engine()
    fixture = await seed_tenant(engine)
    return engine, fixture, DiscoveryService(engine)


async def test_independent_sightings_merge_into_one_candidate() -> None:
    engine, fixture, service = await _service_and_tenant()
    try:
        first = await service.observe(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            locator=f"{ZIE}/tree/main/workflows",
            discovered_by="RESEARCH_MISSION",
            observed_via="RESEARCH_PROVIDER",
            observer_ref="run-1",
        )
        second = await service.observe(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            locator=f"{ZIE}/issues/42",
            discovered_by="OPERATOR",
            observed_via="OPERATOR_SUBMISSION",
            observer_ref="run-2",
        )
        assert first.candidate_id == second.candidate_id
        assert second.observation_count == 2
        assert second.normalized_identity_key == "github:zie619/n8n-workflows"
        assert set(second.discovery_refs) == {"run-1", "run-2"}
    finally:
        await engine.dispose()


async def test_history_is_append_only_and_densely_sequenced() -> None:
    engine, fixture, service = await _service_and_tenant()
    try:
        candidate = await service.observe(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            locator=ZIE,
            discovered_by="RESEARCH_MISSION",
            observed_via="RESEARCH_PROVIDER",
        )
        for state, reason in (
            ("TRIAGED", "triage"),
            ("PROVENANCE_CHECKED", "provenance"),
            ("CONTENT_ACQUIRED", "acquired"),
        ):
            await service.advance(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                candidate_id=candidate.candidate_id,
                to_state=state,
                reason_code=reason,
            )
        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            history = await DiscoveryRepository().list_transitions(
                uow.connection, candidate_id=candidate.candidate_id
            )
        assert [row.sequence for row in history] == [1, 2, 3, 4]
        assert [row.to_state for row in history] == [
            "DISCOVERED",
            "TRIAGED",
            "PROVENANCE_CHECKED",
            "CONTENT_ACQUIRED",
        ]
        assert all(row.decision_hash for row in history)
    finally:
        await engine.dispose()


async def test_illegal_transition_is_refused() -> None:
    engine, fixture, service = await _service_and_tenant()
    try:
        candidate = await service.observe(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            locator=ZIE,
            discovered_by="RESEARCH_MISSION",
            observed_via="RESEARCH_PROVIDER",
        )
        with pytest.raises(DdeError) as excinfo:
            await service.advance(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                candidate_id=candidate.candidate_id,
                to_state="ADMITTED",
                reason_code="skip.everything",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


async def test_a_passing_trial_advances_lifecycle_but_never_raises_trust() -> None:
    engine, fixture, service = await _service_and_tenant()
    try:
        candidate = await service.observe(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            locator=ZIE,
            discovered_by="RESEARCH_MISSION",
            observed_via="RESEARCH_PROVIDER",
        )
        trust_before = candidate.source_trust
        assert trust_before == "S7_DISCOVERY_ONLY"
        for state in (
            "TRIAGED",
            "PROVENANCE_CHECKED",
            "CONTENT_ACQUIRED",
        ):
            await service.advance(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                candidate_id=candidate.candidate_id,
                to_state=state,
                reason_code="step",
            )
        await service.sanitize(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            candidate_id=candidate.candidate_id,
            findings=[{"finding_class": "NOTE", "detail": "clean"}],
        )
        await service.advance(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            candidate_id=candidate.candidate_id,
            to_state="ARCHITECTURE_CHECKED",
            reason_code="architecture",
            architecture_findings=[{"finding_class": "NOTE"}],
        )
        await service.advance(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            candidate_id=candidate.candidate_id,
            to_state="TRIAL_ELIGIBLE",
            reason_code="eligible",
        )
        trial = await service.open_trial(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            candidate_id=candidate.candidate_id,
            trial_kind="IMPORT_SMOKE",
            sandbox_profile="bounded",
            command=["python", "-c", "pass"],
        )
        after = await service.complete_trial(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            trial=trial,
            outcome="PASSED",
        )
        assert after.lifecycle_state == "SANDBOX_TESTED"
        assert after.source_trust == trust_before
    finally:
        await engine.dispose()


async def test_blocking_sanitizer_finding_rejects_instead_of_advancing() -> None:
    engine, fixture, service = await _service_and_tenant()
    try:
        candidate = await service.observe(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            locator=ZIE,
            discovered_by="RESEARCH_MISSION",
            observed_via="RESEARCH_PROVIDER",
        )
        for state in ("TRIAGED", "PROVENANCE_CHECKED", "CONTENT_ACQUIRED"):
            await service.advance(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                candidate_id=candidate.candidate_id,
                to_state=state,
                reason_code="step",
            )
        rejected = await service.sanitize(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            candidate_id=candidate.candidate_id,
            findings=[{"finding_class": "PROMPT_INJECTION", "detail": "readme"}],
        )
        assert rejected.lifecycle_state == "REJECTED"
    finally:
        await engine.dispose()


async def test_anti_pattern_admission_stays_retrievable_without_positive_slots() -> (
    None
):
    engine, fixture, service = await _service_and_tenant()
    try:
        candidate = await service.observe(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            locator=ZIE,
            discovered_by="RESEARCH_MISSION",
            observed_via="RESEARCH_PROVIDER",
        )
        for state in (
            "TRIAGED",
            "PROVENANCE_CHECKED",
            "CONTENT_ACQUIRED",
            "SANITIZED",
            "ARCHITECTURE_CHECKED",
        ):
            await service.advance(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                candidate_id=candidate.candidate_id,
                to_state=state,
                reason_code="step",
            )
        qualification, final = await service.qualify(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            candidate_id=candidate.candidate_id,
            disposition="ADMIT_ANTI_PATTERN",
            rationale="useful only as a failure signature",
        )
        assert qualification.guidance_polarity == "ANTI_PATTERN"
        assert "NORMATIVE_IMPLEMENTATION" in qualification.forbidden_uses
        assert "FAILURE_SIGNATURE" in qualification.allowed_uses
        assert final.lifecycle_state == "ADMITTED"
        assert final.source_id is not None

        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(graph_trust_projections).where(
                            graph_trust_projections.c.candidate_id
                            == candidate.candidate_id
                        )
                    )
                )
                .mappings()
                .one()
            )
        assert row["retrievable"] is True
        assert row["satisfies_positive_slots"] is False
    finally:
        await engine.dispose()


async def test_qualification_can_never_exceed_candidate_trust() -> None:
    engine, fixture, service = await _service_and_tenant()
    try:
        candidate = await service.observe(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            locator=ZIE,
            discovered_by="RESEARCH_MISSION",
            observed_via="RESEARCH_PROVIDER",
        )
        for state in (
            "TRIAGED",
            "PROVENANCE_CHECKED",
            "CONTENT_ACQUIRED",
            "SANITIZED",
            "ARCHITECTURE_CHECKED",
        ):
            await service.advance(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                candidate_id=candidate.candidate_id,
                to_state=state,
                reason_code="step",
            )
        qualification, _ = await service.qualify(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            candidate_id=candidate.candidate_id,
            disposition="ADMIT_POSITIVE_GUIDANCE",
            rationale="asking for more authority than the source can carry",
            requested_ceiling="S1_NORMATIVE",
        )
        assert qualification.authority_ceiling == "S7_DISCOVERY_ONLY"
    finally:
        await engine.dispose()


async def test_discovery_rows_are_invisible_to_another_project() -> None:
    """Proved through `dde_rls_probe`, never through the superuser owner role.

    The local `dde` role is a superuser and bypasses RLS, so a SELECT as `dde`
    is not evidence that a policy holds — the existing Chapter 13.9 suite makes
    the same point.

    This claims cross-project invisibility only. The unset-GUC case is already
    covered for every stored table by `test_rls_enforcement`, which enumerates
    the schema registry and therefore picked these tables up automatically.
    """
    engine = new_engine()
    service = DiscoveryService(engine)
    try:
        fixture = await seed_tenant(engine)
        other = await seed_tenant(engine)
        probe_url = await ensure_rls_probe_role(engine)
        probe_engine = create_async_engine(probe_url)
        try:
            candidate = await service.observe(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                locator=ZIE,
                discovered_by="RESEARCH_MISSION",
                observed_via="RESEARCH_PROVIDER",
            )
            async with open_rls_probe(
                probe_engine,
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
            ) as connection:
                own = (
                    await connection.execute(
                        select(discovery_candidates.c.candidate_id)
                    )
                ).all()
            assert (candidate.candidate_id,) in own

            async with open_rls_probe(
                probe_engine, tenant_id=other.tenant_id, project_id=other.project_id
            ) as connection:
                foreign = (
                    await connection.execute(
                        select(discovery_candidates.c.candidate_id)
                    )
                ).all()
            assert foreign == []

        finally:
            await probe_engine.dispose()
    finally:
        await engine.dispose()
