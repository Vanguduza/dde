"""Production capability registry -- the sole writer of `capabilities` rows
in PostgreSQL (Chapter 3.5, 3.8, 9.1). DDE-016's full scope, no more.

**What this module is.** Chapter 9.1's `CapabilityDescriptor` catalog:
`register()` validates and persists a declared, admitted, versioned
side-effecting operation (Chapter 9.3's mandatory `side_effect_class`
taxonomy enforced as a real, rejecting enum -- "a capability without a
declared class cannot be admitted"), and `deprecate()`/`retire()` walk its
real (if blueprint-underspecified -- see `engine.capabilities.taxonomy`'s
module docstring) lifecycle. Follows the same service-class +
`PostgresUnitOfWork` shape as `engine.verification.oracle.
AcceptanceOracleService` and `engine.integration.service.
WriteScopeLeaseService`: each public method opens and commits its own unit
of work unless one is supplied, so a caller composing a cross-module
transaction (Chapter 3.5) can share it instead.

**What this module explicitly is NOT** -- deferred to the missions that own
them, not stubbed here:
  - `CapabilityLease` acquisition, evaluation, granting, revocation or
    expiry (Chapter 9.2) -- DDE-017. This mission never issues, checks or
    even models a lease; `capability_id`/`capability_version` are the two
    fields 9.2 says a lease references, and this registry is what gives
    those two fields a real row to reference, nothing more.
  - The T1 capability gateway that would validate a lease, check scope,
    journal an effect and broker a credential per call (Chapter 7.2) --
    DDE-017. Nothing in this module intercepts or brokers a real call.
  - T2 containment -- egress proxy, ambient-credential elimination,
    seccomp/container isolation (Chapter 7.2, 9.1's `enforcement_tier`
    stores the *declared* tier only) -- DDE-018.
  - The Credential Broker (Chapter 14.3) -- DDE-019.
  - Chapter 9.5's tool admission pipeline execution (discover -> static
    scan -> provenance -> permission review -> sandbox trial -> benchmark
    -> conformance test -> certify -> register) and Chapter 9.6's
    dependency/SBOM admission gates -- DDE-020/DDE-021. `register()` is
    that pipeline's *last* step only ("register"); `certification_status`
    is a required, validated column on the row, but nothing in this module
    runs a static scan, a sandbox trial or a benchmark. A caller supplies
    the outcome; this service does not produce it.
  - Chapter 9.7's mandatory diff gates (Gitleaks, Semgrep, licence/
    provenance, forbidden-path) -- a separate, always-on CI concern per
    that section's own text ("blocking verification steps rather than
    registry entries"), not a capability registry responsibility at all.
  - Retrofitting any Stage 1 module (`engine.workers`, `engine.execution`,
    `engine.routing`) to require a lease before acting. `ExecutionPlan.
    capability_requirements[]` and `engine.routing.policy`'s
    `CAPABILITY_REPOSITORY`/`CAPABILITY_TESTING`/`CAPABILITY_BROWSER`
    string constants already use exactly this registry's `capability_id`
    shape (e.g. `"capability.repository"`) -- this mission's seed data
    (`engine.capabilities.seed`) registers real descriptors under
    matching names, but nothing reads `capability_requirements` and
    resolves it against this table. That resolution is DDE-017's job.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.hashing import descriptor_hash
from engine.capabilities.repository import CapabilityRepository
from engine.capabilities.states import LIFECYCLE_TRANSITIONS
from engine.capabilities.taxonomy import (
    CERTIFICATION_STATUSES,
    ENFORCEMENT_TIERS,
    RISK_CLASSES,
    SIDE_EFFECT_CLASSES,
    VISIBILITIES,
)
from engine.contracts.capability_descriptor import CapabilityDescriptor
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.events.service import EventService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")


class CapabilityRegistryService:
    """Async, PostgreSQL-backed writer for `capabilities` (Chapter 3.8:
    definition immutable per version, lifecycle mutable). `tenant_id`/
    `project_id` here scope the *acting principal's* transaction GUC and
    the `CapabilityRegistered`/`CapabilityDescriptorDeprecated`/
    `CapabilityDescriptorTransitioned` audit event this service appends
    (`events`/`outbox` require a real `project_id`, Chapter 3.2's "every
    mission-scoped and runtime table") -- never the row itself.
    `capabilities` is a Chapter 3.2 global registry with no `tenant_id`/
    `project_id` columns of its own; a private (`visibility="tenant"`)
    descriptor is scoped instead by its own `owner_tenant_id` column."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: CapabilityRepository | None = None,
        events: EventService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or CapabilityRepository()
        self._events = events or EventService(engine)
        self._clock = clock or SystemClock()

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await body(owned)
            await owned.commit()
            return result

    async def register(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        capability_id: str,
        version: str,
        category: str,
        summary: str,
        side_effect_class: str,
        risk_class: str,
        enforcement_tier: str,
        registered_by: str,
        interface_schema_ref: str | None = None,
        input_schema_ref: str | None = None,
        output_schema_ref: str | None = None,
        implementations: list[str] | None = None,
        supported_worker_profiles: list[str] | None = None,
        supported_environments: list[str] | None = None,
        supported_workloads: list[str] | None = None,
        permission_model: dict[str, object] | None = None,
        cost_model: dict[str, object] | None = None,
        network_requirements: dict[str, object] | None = None,
        dependencies: list[str] | None = None,
        provenance: dict[str, object] | None = None,
        certification_status: str = "PENDING",
        visibility: str = "global",
        owner_tenant_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> CapabilityDescriptor:
        """Chapter 9.1's descriptor, admitted. Idempotent for an identical
        re-registration of the same `(capability_id, version)` (Chapter
        3.10: definitions are content-hashed); rejects a genuinely
        different re-registration under the same `(capability_id,
        version)` pair as a duplicate. Registering a new version of an
        already-`ACTIVE` `capability_id` supersedes it: the previous
        version moves to `DEPRECATED` in the same transaction (Chapter
        3.10: "a material change creates a new version ... it never
        overwrites")."""
        if not capability_id:
            raise DdeError("POLICY_DENIED", "capability_id must not be empty")
        if not version:
            raise DdeError("POLICY_DENIED", "version must not be empty")
        if side_effect_class not in SIDE_EFFECT_CLASSES:
            raise DdeError(
                "POLICY_DENIED",
                "Chapter 9.3: a capability without a declared, valid "
                "side_effect_class cannot be admitted",
                details={
                    "side_effect_class": side_effect_class,
                    "allowed": sorted(SIDE_EFFECT_CLASSES),
                },
            )
        if risk_class not in RISK_CLASSES:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown risk_class",
                details={"risk_class": risk_class, "allowed": sorted(RISK_CLASSES)},
            )
        if enforcement_tier not in ENFORCEMENT_TIERS:
            raise DdeError(
                "POLICY_DENIED",
                "Chapter 7.2: a capability descriptor declares T1 or T2 only",
                details={
                    "enforcement_tier": enforcement_tier,
                    "allowed": sorted(ENFORCEMENT_TIERS),
                },
            )
        if certification_status not in CERTIFICATION_STATUSES:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown certification_status",
                details={
                    "certification_status": certification_status,
                    "allowed": sorted(CERTIFICATION_STATUSES),
                },
            )
        if visibility not in VISIBILITIES:
            raise DdeError(
                "POLICY_DENIED",
                "Chapter 3.2: visibility must be 'global' or 'tenant'",
                details={"visibility": visibility, "allowed": sorted(VISIBILITIES)},
            )
        if visibility == "global" and owner_tenant_id is not None:
            raise DdeError(
                "POLICY_DENIED",
                "A global capability cannot declare an owner_tenant_id",
                details={"owner_tenant_id": str(owner_tenant_id)},
            )
        resolved_owner_tenant_id = owner_tenant_id
        if visibility == "tenant" and resolved_owner_tenant_id is None:
            resolved_owner_tenant_id = tenant_id

        implementations = list(implementations or [])
        supported_worker_profiles = list(supported_worker_profiles or [])
        supported_environments = list(supported_environments or [])
        supported_workloads = list(supported_workloads or [])
        permission_model = dict(permission_model or {})
        cost_model = dict(cost_model or {})
        network_requirements = dict(network_requirements or {})
        dependencies = list(dependencies or [])
        provenance = dict(provenance or {})

        computed_hash = descriptor_hash(
            capability_id=capability_id,
            version=version,
            category=category,
            summary=summary,
            interface_schema_ref=interface_schema_ref,
            input_schema_ref=input_schema_ref,
            output_schema_ref=output_schema_ref,
            implementations=implementations,
            supported_worker_profiles=supported_worker_profiles,
            supported_environments=supported_environments,
            supported_workloads=supported_workloads,
            risk_class=risk_class,
            side_effect_class=side_effect_class,
            enforcement_tier=enforcement_tier,
            permission_model=permission_model,
            cost_model=cost_model,
            network_requirements=network_requirements,
            dependencies=dependencies,
            provenance=provenance,
            visibility=visibility,
            owner_tenant_id=resolved_owner_tenant_id,
        )

        async def _op(active: PostgresUnitOfWork) -> CapabilityDescriptor:
            existing = await self._repository.get_by_capability_and_version(
                active.connection, capability_id, version
            )
            if existing is not None:
                if existing.descriptor_hash == computed_hash:
                    return existing
                raise DdeError(
                    "POLICY_DENIED",
                    f"capability_id={capability_id!r} version={version!r} is "
                    "already registered with different definition content",
                    details={
                        "capability_id": capability_id,
                        "version": version,
                        "existing_descriptor_id": str(existing.descriptor_id),
                    },
                )
            previous_active = await self._repository.get_active_by_capability_id(
                active.connection, capability_id
            )
            now = self._clock.now()
            new_id = uuid7()
            record = CapabilityDescriptor(
                descriptor_id=new_id,
                capability_id=capability_id,
                version=version,
                category=category,
                summary=summary,
                interface_schema_ref=interface_schema_ref,
                input_schema_ref=input_schema_ref,
                output_schema_ref=output_schema_ref,
                implementations=implementations,
                supported_worker_profiles=supported_worker_profiles,
                supported_environments=supported_environments,
                supported_workloads=supported_workloads,
                risk_class=risk_class,
                side_effect_class=side_effect_class,
                enforcement_tier=enforcement_tier,
                permission_model=permission_model,
                cost_model=cost_model,
                network_requirements=network_requirements,
                dependencies=dependencies,
                provenance=provenance,
                certification_status=certification_status,
                lifecycle_status="ACTIVE",
                visibility=visibility,
                owner_tenant_id=resolved_owner_tenant_id,
                supersedes_descriptor_id=(
                    previous_active.descriptor_id
                    if previous_active is not None
                    else None
                ),
                superseded_by_descriptor_id=None,
                descriptor_hash=computed_hash,
                registered_by=registered_by,
                deprecated_at=None,
                retired_at=None,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_descriptor(active.connection, record)
            if previous_active is not None:
                rowcount = await self._repository.update_fields(
                    active.connection,
                    previous_active.descriptor_id,
                    fields={
                        "lifecycle_status": "DEPRECATED",
                        "superseded_by_descriptor_id": new_id,
                        "deprecated_at": now,
                        "updated_at": now,
                    },
                )
                if rowcount != 1:
                    raise DdeError(
                        "VERSION_CONFLICT",
                        "Unknown capability descriptor",
                        details={"descriptor_id": str(previous_active.descriptor_id)},
                    )
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type="CapabilityDescriptorDeprecated",
                    aggregate_type="capability_descriptor",
                    aggregate_id=previous_active.descriptor_id,
                    payload={
                        "capability_id": capability_id,
                        "superseded_by_descriptor_id": str(new_id),
                    },
                    uow=active,
                )
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="CapabilityRegistered",
                aggregate_type="capability_descriptor",
                aggregate_id=new_id,
                payload={
                    "capability_id": capability_id,
                    "version": version,
                    "side_effect_class": side_effect_class,
                    "enforcement_tier": enforcement_tier,
                },
                uow=active,
            )
            return record

        return await self._run(uow, tenant_id, project_id, _op)

    async def deprecate(
        self,
        *,
        descriptor: CapabilityDescriptor,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> CapabilityDescriptor:
        return await self._transition(
            descriptor,
            "DEPRECATED",
            tenant_id=tenant_id,
            project_id=project_id,
            uow=uow,
        )

    async def retire(
        self,
        *,
        descriptor: CapabilityDescriptor,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> CapabilityDescriptor:
        return await self._transition(
            descriptor, "RETIRED", tenant_id=tenant_id, project_id=project_id, uow=uow
        )

    async def _transition(
        self,
        descriptor: CapabilityDescriptor,
        target_status: str,
        *,
        tenant_id: UUID,
        project_id: UUID,
        uow: PostgresUnitOfWork | None,
    ) -> CapabilityDescriptor:
        async def _op(active: PostgresUnitOfWork) -> CapabilityDescriptor:
            current = await self._require_descriptor(active, descriptor.descriptor_id)
            next_status = transition(
                current.lifecycle_status, target_status, LIFECYCLE_TRANSITIONS
            )
            now = self._clock.now()
            fields: dict[str, object] = {
                "lifecycle_status": next_status,
                "updated_at": now,
            }
            if next_status == "DEPRECATED":
                fields["deprecated_at"] = now
            elif next_status == "RETIRED":
                fields["retired_at"] = now
            rowcount = await self._repository.update_fields(
                active.connection, current.descriptor_id, fields=fields
            )
            if rowcount != 1:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Unknown capability descriptor",
                    details={"descriptor_id": str(current.descriptor_id)},
                )
            updated = await self._require_descriptor(active, current.descriptor_id)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="CapabilityDescriptorTransitioned",
                aggregate_type="capability_descriptor",
                aggregate_id=updated.descriptor_id,
                payload={
                    "from": current.lifecycle_status,
                    "to": updated.lifecycle_status,
                },
                uow=active,
            )
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_descriptor(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        descriptor_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> CapabilityDescriptor:
        async def _op(active: PostgresUnitOfWork) -> CapabilityDescriptor:
            return await self._require_descriptor(active, descriptor_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_active(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        capability_id: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> CapabilityDescriptor:
        async def _op(active: PostgresUnitOfWork) -> CapabilityDescriptor:
            record = await self._repository.get_active_by_capability_id(
                active.connection, capability_id
            )
            if record is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "No ACTIVE descriptor for this capability_id",
                    details={"capability_id": capability_id},
                )
            return record

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_versions(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        capability_id: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[CapabilityDescriptor]:
        async def _op(active: PostgresUnitOfWork) -> list[CapabilityDescriptor]:
            return await self._repository.list_versions(
                active.connection, capability_id
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_by_category(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        category: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[CapabilityDescriptor]:
        async def _op(active: PostgresUnitOfWork) -> list[CapabilityDescriptor]:
            return await self._repository.list_by_category(active.connection, category)

        return await self._run(uow, tenant_id, project_id, _op)

    async def _require_descriptor(
        self, active: PostgresUnitOfWork, descriptor_id: UUID
    ) -> CapabilityDescriptor:
        record = await self._repository.get_by_id(active.connection, descriptor_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown capability descriptor")
        return record
