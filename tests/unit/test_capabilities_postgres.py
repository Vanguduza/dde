"""PostgreSQL-backed `engine.capabilities`: schema, state-transition,
negative and recovery tests (Chapter 19.1) -- DDE-016's full acceptance
proof.

Exercises `engine.capabilities.service.CapabilityRegistryService` --
the production writer of `capabilities` (Chapter 3.8) -- against a real
database, and `engine.capabilities.seed.seed_capabilities` -- the real,
validated registration path for Chapter 9.8's Stage-1-relevant seed
portfolio.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from engine.capabilities.repository import CapabilityRepository
from engine.capabilities.seed import SEED_CAPABILITIES, seed_capabilities
from engine.capabilities.service import CapabilityRegistryService
from engine.core.errors import DdeError
from engine.truth.db import open_unit_of_work
from tests.support.db import ensure_rls_probe_role, new_engine, seed_tenant


@pytest.mark.asyncio
async def test_schema_round_trip_persists_declared_columns() -> None:
    """A row read back from the real table validates against the JSON-
    schema-generated contract with no drift (Chapter 3.1) -- the schema
    test."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = CapabilityRegistryService(engine)
        registered = await service.register(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id=f"capability.schema-round-trip-{uuid4().hex}",
            version="1",
            category="process",
            summary="Schema round trip is provable against the real table.",
            side_effect_class="WORKSPACE_LOCAL",
            risk_class="low",
            enforcement_tier="T1",
            implementations=["engine.environments.backends.local_process"],
            supported_workloads=["bulk_implementation"],
            network_requirements={"egress": "none"},
            registered_by="system:test",
        )
        async with open_unit_of_work(
            engine, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        ) as uow:
            reloaded = await CapabilityRepository().get_by_id(
                uow.connection, registered.descriptor_id
            )
            await uow.commit()
        assert reloaded == registered
        assert reloaded is not None
        assert reloaded.lifecycle_status == "ACTIVE"
        assert reloaded.visibility == "global"
        assert reloaded.owner_tenant_id is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_registering_the_same_definition_twice_is_idempotent() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = CapabilityRegistryService(engine)
        capability_id = f"capability.idempotent-{uuid4().hex}"
        first = await service.register(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id=capability_id,
            version="1",
            category="process",
            summary="Same definition, registered twice.",
            side_effect_class="PURE_READ",
            risk_class="low",
            enforcement_tier="T1",
            registered_by="system:test",
        )
        second = await service.register(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id=capability_id,
            version="1",
            category="process",
            summary="Same definition, registered twice.",
            side_effect_class="PURE_READ",
            risk_class="low",
            enforcement_tier="T1",
            registered_by="system:test",
        )
        assert second.descriptor_id == first.descriptor_id
        assert second.descriptor_hash == first.descriptor_hash
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_missing_side_effect_class_is_rejected() -> None:
    """Chapter 9.3: "A capability without a declared class cannot be
    admitted." AGENTS.md's Definition of Done requires exactly this
    negative test."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = CapabilityRegistryService(engine)
        with pytest.raises(DdeError) as excinfo:
            await service.register(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                capability_id=f"capability.negative-{uuid4().hex}",
                version="1",
                category="process",
                summary="Missing side_effect_class must be rejected.",
                side_effect_class="",
                risk_class="low",
                enforcement_tier="T1",
                registered_by="system:test",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_invalid_side_effect_class_is_rejected() -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = CapabilityRegistryService(engine)
        with pytest.raises(DdeError) as excinfo:
            await service.register(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                capability_id=f"capability.negative-{uuid4().hex}",
                version="1",
                category="process",
                summary="Invalid side_effect_class must be rejected.",
                side_effect_class="SOMETHING_MADE_UP",
                risk_class="low",
                enforcement_tier="T1",
                registered_by="system:test",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
        assert excinfo.value.details is not None
        assert excinfo.value.details["side_effect_class"] == "SOMETHING_MADE_UP"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_duplicate_registration_with_different_content_is_rejected() -> (
    None
):
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = CapabilityRegistryService(engine)
        capability_id = f"capability.duplicate-{uuid4().hex}"
        await service.register(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id=capability_id,
            version="1",
            category="process",
            summary="Original definition.",
            side_effect_class="PURE_READ",
            risk_class="low",
            enforcement_tier="T1",
            registered_by="system:test",
        )
        with pytest.raises(DdeError) as excinfo:
            await service.register(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                capability_id=capability_id,
                version="1",
                category="process",
                summary="A genuinely different definition, same version.",
                side_effect_class="PURE_READ",
                risk_class="low",
                enforcement_tier="T1",
                registered_by="system:test",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negative_invalid_enforcement_tier_is_rejected() -> None:
    """`audit_only` is a valid `ExecutionPlan.enforcement_tier` (Chapter
    7.2) but not a valid capability descriptor's own declared tier."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = CapabilityRegistryService(engine)
        with pytest.raises(DdeError) as excinfo:
            await service.register(
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
                capability_id=f"capability.negative-{uuid4().hex}",
                version="1",
                category="process",
                summary="audit_only is not a capability descriptor enforcement_tier.",
                side_effect_class="PURE_READ",
                risk_class="low",
                enforcement_tier="audit_only",
                registered_by="system:test",
            )
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_registering_new_version_deprecates_previous_active_version() -> None:
    """State-transition test: Chapter 3.10's "a material change creates a
    new version ... it never overwrites", proven with a real second
    registration under the same `capability_id`."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = CapabilityRegistryService(engine)
        capability_id = f"capability.supersede-{uuid4().hex}"
        v1 = await service.register(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id=capability_id,
            version="1",
            category="process",
            summary="Version 1.",
            side_effect_class="PURE_READ",
            risk_class="low",
            enforcement_tier="T1",
            registered_by="system:test",
        )
        assert v1.lifecycle_status == "ACTIVE"
        assert v1.supersedes_descriptor_id is None

        v2 = await service.register(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id=capability_id,
            version="2",
            category="process",
            summary="Version 2, a genuinely different definition.",
            side_effect_class="WORKSPACE_LOCAL",
            risk_class="low",
            enforcement_tier="T1",
            registered_by="system:test",
        )
        assert v2.lifecycle_status == "ACTIVE"
        assert v2.supersedes_descriptor_id == v1.descriptor_id

        reloaded_v1 = await service.get_descriptor(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            descriptor_id=v1.descriptor_id,
        )
        assert reloaded_v1.lifecycle_status == "DEPRECATED"
        assert reloaded_v1.superseded_by_descriptor_id == v2.descriptor_id
        assert reloaded_v1.deprecated_at is not None

        active = await service.get_active(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id=capability_id,
        )
        assert active.descriptor_id == v2.descriptor_id

        versions = await service.list_versions(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id=capability_id,
        )
        assert [item.version for item in versions] == ["1", "2"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_retire_transitions_and_illegal_transition_is_rejected() -> None:
    """`ACTIVE -> RETIRED` is real and durable; `RETIRED` is terminal --
    a transition attempted out of it is refused as a typed error, never
    silently applied."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = CapabilityRegistryService(engine)
        descriptor = await service.register(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id=f"capability.retire-{uuid4().hex}",
            version="1",
            category="process",
            summary="Will be retired.",
            side_effect_class="PURE_READ",
            risk_class="low",
            enforcement_tier="T1",
            registered_by="system:test",
        )
        retired = await service.retire(
            descriptor=descriptor,
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
        )
        assert retired.lifecycle_status == "RETIRED"
        assert retired.retired_at is not None

        with pytest.raises(DdeError) as excinfo:
            await service.retire(
                descriptor=retired,
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
            )
        assert excinfo.value.error_code == "VERSION_CONFLICT"

        with pytest.raises(DdeError) as excinfo_deprecate:
            await service.deprecate(
                descriptor=retired,
                tenant_id=fixture.tenant_id,
                project_id=fixture.project_id,
            )
        assert excinfo_deprecate.value.error_code == "VERSION_CONFLICT"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seed_capabilities_registers_and_reads_back_real_rows() -> None:
    """Chapter 9.8's Stage-1-relevant seed portfolio, registered through
    the real, validated `register()` path (never a hand-written SQL
    `INSERT`), then read back."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = CapabilityRegistryService(engine)
        registered = await seed_capabilities(
            service, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        )
        assert len(registered) == len(SEED_CAPABILITIES)
        capability_ids = {item.capability_id for item in registered}
        assert capability_ids == {spec.capability_id for spec in SEED_CAPABILITIES}
        for item in registered:
            assert item.lifecycle_status == "ACTIVE"
            assert item.certification_status == "CERTIFIED"
            assert item.side_effect_class
            assert item.visibility == "global"

        active = await service.get_active(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id="capability.git_operations",
        )
        assert active.side_effect_class == "EXTERNAL_IDEMPOTENT"
        assert active.enforcement_tier == "T1"
        assert "git" in active.dependencies

        # Re-seeding is idempotent: same rows come back, not duplicates.
        again = await seed_capabilities(
            service, tenant_id=fixture.tenant_id, project_id=fixture.project_id
        )
        assert {item.descriptor_id for item in again} == {
            item.descriptor_id for item in registered
        }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_second_session_sees_the_exact_committed_descriptor() -> None:
    """Chapter 19.1's recovery test type: a descriptor committed by one
    session (engine/connection pool) is read back identically by a fresh
    one."""
    writer_engine = new_engine()
    fixture = await seed_tenant(writer_engine)
    service = CapabilityRegistryService(writer_engine)
    registered = await service.register(
        tenant_id=fixture.tenant_id,
        project_id=fixture.project_id,
        capability_id=f"capability.recovery-{uuid4().hex}",
        version="1",
        category="filesystem",
        summary="Recovery test descriptor.",
        side_effect_class="WORKSPACE_LOCAL",
        risk_class="low",
        enforcement_tier="T1",
        registered_by="system:test",
    )
    await writer_engine.dispose()

    reader_engine = new_engine()
    try:
        reader_service = CapabilityRegistryService(reader_engine)
        reloaded = await reader_service.get_descriptor(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            descriptor_id=registered.descriptor_id,
        )
        assert reloaded == registered
    finally:
        await reader_engine.dispose()


@pytest.mark.asyncio
async def test_global_capability_visible_tenant_capability_hidden_without_guc() -> None:
    """Chapter 3.2's global-registry RLS rule: a `visibility="global"` row
    is visible without a tenant GUC; a `visibility="tenant"` row is not
    (fail-closed, exactly like every other tenant-scoped table's RLS)."""
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        service = CapabilityRegistryService(engine)
        global_descriptor = await service.register(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id=f"capability.global-{uuid4().hex}",
            version="1",
            category="process",
            summary="Globally visible capability.",
            side_effect_class="PURE_READ",
            risk_class="low",
            enforcement_tier="T1",
            registered_by="system:test",
            visibility="global",
        )
        tenant_descriptor = await service.register(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            capability_id=f"capability.tenant-private-{uuid4().hex}",
            version="1",
            category="process",
            summary="Tenant-private capability.",
            side_effect_class="PURE_READ",
            risk_class="low",
            enforcement_tier="T1",
            registered_by="system:test",
            visibility="tenant",
        )
        assert tenant_descriptor.owner_tenant_id == fixture.tenant_id

        probe_url = await ensure_rls_probe_role(engine)
        probe_engine = create_async_engine(probe_url)
        try:
            async with probe_engine.connect() as connection, connection.begin():
                global_visible = await connection.execute(
                    text("SELECT 1 FROM capabilities WHERE descriptor_id = :id"),
                    {"id": global_descriptor.descriptor_id},
                )
                assert global_visible.first() is not None

                tenant_visible = await connection.execute(
                    text("SELECT 1 FROM capabilities WHERE descriptor_id = :id"),
                    {"id": tenant_descriptor.descriptor_id},
                )
                assert tenant_visible.first() is None
        finally:
            await probe_engine.dispose()
    finally:
        await engine.dispose()
