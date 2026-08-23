"""Chapter 11.6 ProductEnvironment lifecycle service.

Owner of `product_environments` and `seed_datasets` rows (Chapter 3.8:
owner `verification`, mutable "lifecycle only"). Every status change goes
through `engine.product_env.states.PRODUCT_ENV_TRANSITIONS` at this, the
single mutation call site; illegal transitions are refused with a typed
Chapter 15.5 error and the row is left untouched.

Chapter 11.6 rules wired here:
- production-class provisioning refuses worker-originated requests
  (FORBIDDEN) and any ExecutionEnvironment reachability binding;
- every ephemeral_preview carries a TTL; `teardown_expired` is the
  destruction sweep and appends a `ProductEnvironmentAbandoned` event on
  the existing EventService (the monitored-metric feed);
- seed datasets are versioned, content-hashed artifacts; seeding twice
  from the same dataset identity yields an identical observable-state
  fingerprint (reproducibility for invariant failures);
- READY requires bidirectional migration verification — both halves of
  `migration_verification` verified, not just the empty-database half;
- failure snapshots are recorded as evidence-artifact references with
  content hashes (retention/WORM wiring itself is Chapter 17.5).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.product_environment import (
    FailureSnapshot,
    ProductEnvironment,
)
from engine.contracts.seed_dataset import SeedDataset
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.product_env.repository import ProductEnvRepository
from engine.product_env.states import assert_transition
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

#: Chapter 15.4 principal classes allowed to request an environment.
HUMAN_ORIGIN = "human"
SERVICE_ORIGIN = "service"
WORKER_ORIGIN = "worker"

#: Classes whose provisioning is reserved to human/service principals.
_PRODUCTION_CLASSES = frozenset({"production", "staging"})

#: The one environment class Chapter 11.6 binds to TTL destruction.
EPHEMERAL_PREVIEW = "ephemeral_preview"

T = TypeVar("T")


def _verification_payload(
    empty_verified: bool,
    previous_verified: bool,
) -> dict[str, object]:
    now = datetime.now().isoformat()
    return {
        "forward_empty": {
            "verified": empty_verified,
            "verified_at": now if empty_verified else None,
        },
        "forward_previous": {
            "verified": previous_verified,
            "verified_at": now if previous_verified else None,
        },
    }


def _both_halves_verified(verification: object) -> bool:
    """True only when BOTH Chapter 11.6 halves verified.

    Accepts either the parsed nested contract or a plain dict (the JSONB
    round-trip shape), because PostgreSQL returns jsonb as dict values.
    """
    if verification is None:
        return False
    if isinstance(verification, dict):
        empty = verification.get("forward_empty")
        previous = verification.get("forward_previous")
        return bool(
            isinstance(empty, dict)
            and empty.get("verified") is True
            and isinstance(previous, dict)
            and previous.get("verified") is True
        )
    forward_empty = getattr(verification, "forward_empty", None)
    forward_previous = getattr(verification, "forward_previous", None)
    if forward_empty is None or forward_previous is None:
        return False
    empty_verified = getattr(forward_empty, "verified", None)
    if empty_verified is None and isinstance(forward_empty, dict):
        empty_verified = forward_empty.get("verified")
    previous_verified = getattr(forward_previous, "verified", None)
    if previous_verified is None and isinstance(forward_previous, dict):
        previous_verified = forward_previous.get("verified")
    return bool(empty_verified is True and previous_verified is True)


def _half_verified(half: object) -> bool:
    verified = getattr(half, "verified", None)
    if verified is None and isinstance(half, dict):
        verified = half.get("verified")
    return bool(verified is True)


def _verification_detail(verification: object) -> dict[str, object]:
    if isinstance(verification, dict):
        return {
            "forward_empty": verification.get("forward_empty", {}).get("verified")
            if isinstance(verification.get("forward_empty"), dict)
            else False,
            "forward_previous": verification.get("forward_previous", {}).get("verified")
            if isinstance(verification.get("forward_previous"), dict)
            else False,
        }
    return {
        "forward_empty": _half_verified(getattr(verification, "forward_empty", None)),
        "forward_previous": _half_verified(
            getattr(verification, "forward_previous", None)
        ),
    }


class ProductEnvironmentService:
    """Async, PostgreSQL-backed writer for Chapter 11.6 rows. Each public
    method opens and commits its own unit of work unless one is supplied,
    matching every sibling service in this codebase."""

    def __init__(
        self,
        engine: AsyncEngine,
        repository: ProductEnvRepository | None = None,
        events: EventService | None = None,
        clock: Clock | None = None,
        base_url_template: str = "https://preview.dde.local/{env_id}",
    ) -> None:
        self._engine = engine
        self._repository = repository or ProductEnvRepository()
        self._events = events or EventService(engine)
        self._clock = clock or SystemClock()
        self._base_url_template = base_url_template

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

    # --- provision ---------------------------------------------------------

    async def provision(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        env_class: str,
        source_revision: str,
        build_artifact_ref: str,
        runtime_topology_ref: dict[str, object],
        datastore_ref: str,
        requested_by_origin: str,
        ttl_seconds: int | None = None,
        mission_id: UUID | None = None,
        seed_dataset_id: UUID | None = None,
        credentials_profile_id: UUID | None = None,
        execution_environment_binding: str | None = None,
        idempotency_key: str | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> ProductEnvironment:
        """Create a ProductEnvironment in PROVISIONING (Chapter 11.6).

        Refusal sites (typed, negative-tested):
        - worker origin + production class -> FORBIDDEN;
        - any ExecutionEnvironment binding -> FORBIDDEN ("never reachable
          from an ExecutionEnvironment");
        - ephemeral_preview without a TTL -> POLICY_DENIED.
        """
        if execution_environment_binding is not None:
            raise DdeError(
                "FORBIDDEN",
                "ProductEnvironments are never reachable from an "
                "ExecutionEnvironment (Chapter 11.6)",
                details={
                    "execution_environment_binding": execution_environment_binding
                },
            )
        if requested_by_origin == WORKER_ORIGIN and env_class in _PRODUCTION_CLASSES:
            raise DdeError(
                "FORBIDDEN",
                "Production-class ProductEnvironments are never provisioned "
                "by a worker (Chapter 11.6)",
                details={"class": env_class, "origin": requested_by_origin},
            )
        if env_class == EPHEMERAL_PREVIEW and ttl_seconds is None:
            raise DdeError(
                "POLICY_DENIED",
                "Every ephemeral preview carries a TTL (Chapter 11.6)",
                details={"class": env_class},
            )

        key = idempotency_key or f"product-env:provision:{uuid7()}"

        async def _op(active: PostgresUnitOfWork) -> ProductEnvironment:
            existing = await self._repository.find_by_idempotency_key(
                active.connection, tenant_id, project_id, key
            )
            if existing is not None:
                return existing
            now = self._clock.now()
            record = ProductEnvironment(
                product_env_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                **{"class": env_class},
                source_revision=source_revision,
                build_artifact_ref=build_artifact_ref,
                runtime_topology_ref=runtime_topology_ref,
                datastore_ref=datastore_ref,
                seed_dataset_id=seed_dataset_id,
                migration_state="PENDING_BASELINE",
                base_url=None,
                credentials_profile_id=credentials_profile_id,
                status="PROVISIONING",
                ttl_expires_at=(
                    now + timedelta(seconds=ttl_seconds)
                    if ttl_seconds is not None
                    else None
                ),
                idempotency_key=key,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_product_environment(active.connection, record)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ProductEnvironmentProvisioningStarted",
                aggregate_type="product_environment",
                aggregate_id=record.product_env_id,
                mission_id=mission_id,
                payload={"class": env_class, "source_revision": source_revision},
                uow=active,
            )
            return record

        return await self._run(uow, tenant_id, project_id, _op)

    # --- migration ---------------------------------------------------------

    async def apply_migrations_forward(
        self,
        record: ProductEnvironment,
        *,
        empty_verified: bool = True,
        previous_verified: bool = False,
        uow: PostgresUnitOfWork | None = None,
    ) -> ProductEnvironment:
        """Record the outcome of the two mandatory verification halves.

        The verifier (`engine.product_env.verification.MigrationVerifier`)
        performs the actual forward-applies; this mutation site records
        them. Only after BOTH halves verify may the row leave MIGRATING
        toward SEEDING/READY.
        """

        async def _op(active: PostgresUnitOfWork) -> ProductEnvironment:
            current = await self._require(active, record.product_env_id)
            assert_transition(current.status, "MIGRATING")
            verification = _verification_payload(empty_verified, previous_verified)
            migration_state = (
                "FORWARD_VERIFIED_PREVIOUS_SCHEMA"
                if empty_verified and previous_verified
                else "PENDING_BASELINE"
            )
            now = self._clock.now()
            await self._repository.update_lifecycle(
                active.connection,
                current.product_env_id,
                status="MIGRATING",
                migration_state=migration_state,
                migration_verification=verification,
                updated_at=now,
            )
            return await self._require(active, current.product_env_id)

        return await self._run(uow, record.tenant_id, record.project_id, _op)

    # --- seeding -----------------------------------------------------------

    async def seed(
        self,
        record: ProductEnvironment,
        *,
        slug: str,
        content_hash: str,
        artifact_ref: str,
        created_by: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> ProductEnvironment:
        """Bind a versioned, content-hashed seed dataset (creating the
        dataset row on first use) and move to SEEDING."""

        async def _op(active: PostgresUnitOfWork) -> ProductEnvironment:
            current = await self._require(active, record.product_env_id)
            assert_transition(current.status, "SEEDING")
            dataset = await self._repository.find_seed_dataset(
                active.connection,
                tenant_id=current.tenant_id,
                project_id=current.project_id,
                slug=slug,
                content_hash=content_hash,
            )
            if dataset is None:
                dataset = SeedDataset(
                    dataset_id=uuid7(),
                    tenant_id=current.tenant_id,
                    project_id=current.project_id,
                    slug=slug,
                    version=1,
                    content_hash=content_hash,
                    artifact_ref=artifact_ref,
                    supersedes_dataset_id=None,
                    status="ACTIVE",
                    created_by=created_by,
                    created_at=self._clock.now(),
                )
                await self._repository.insert_seed_dataset(active.connection, dataset)
            now = self._clock.now()
            await self._repository.update_lifecycle(
                active.connection,
                current.product_env_id,
                status="SEEDING",
                seed_dataset_id=dataset.dataset_id,
                updated_at=now,
            )
            return await self._require(active, current.product_env_id)

        return await self._run(uow, record.tenant_id, record.project_id, _op)

    async def observable_state_fingerprint(
        self,
        record: ProductEnvironment,
        *,
        uow: PostgresUnitOfWork | None = None,
    ) -> str:
        """Deterministic observable state of the seeded datastore.

        The fingerprint is the bound dataset's identity + content hash —
        the same dataset must therefore always produce the same value,
        which is exactly the reproducibility property Chapter 11.6 demands
        ("so an invariant failure is reproducible").
        """

        async def _op(active: PostgresUnitOfWork) -> str:
            current = await self._require(active, record.product_env_id)
            if current.seed_dataset_id is None:
                raise DdeError("POLICY_DENIED", "environment has no bound seed dataset")
            dataset = await self._repository.get_seed_dataset(
                active.connection, current.seed_dataset_id
            )
            if dataset is None:
                raise DdeError("POLICY_DENIED", "bound seed dataset is missing")
            return sha256_hex(
                f"{dataset.slug}:{dataset.version}:{dataset.content_hash}"
            )

        return await self._run(uow, record.tenant_id, record.project_id, _op)

    # --- readiness / use ---------------------------------------------------

    async def mark_ready(
        self,
        record: ProductEnvironment,
        *,
        uow: PostgresUnitOfWork | None = None,
    ) -> ProductEnvironment:
        async def _op(active: PostgresUnitOfWork) -> ProductEnvironment:
            current = await self._require(active, record.product_env_id)
            # The bidirectional-verification gate is checked BEFORE the
            # transition table so a too-early READY attempt reports the
            # semantic reason (which halves are unverified), not merely an
            # illegal-transition code (Chapter 11.6: a migration verified
            # only on an empty database is not verified).
            verification = current.migration_verification
            both_verified = _both_halves_verified(verification)
            if not both_verified:
                raise DdeError(
                    "POLICY_DENIED",
                    "Migration verification is mandatory and bidirectional; "
                    "a migration verified only on an empty database is not "
                    "verified (Chapter 11.6)",
                    details=_verification_detail(verification),
                )
            assert_transition(current.status, "READY")
            now = self._clock.now()
            base_url = self._base_url_template.format(
                env_id=str(current.product_env_id)
            )
            await self._repository.update_lifecycle(
                active.connection,
                current.product_env_id,
                status="READY",
                base_url=base_url,
                updated_at=now,
            )
            return await self._require(active, current.product_env_id)

        return await self._run(uow, record.tenant_id, record.project_id, _op)

    async def mark_in_use(
        self,
        record: ProductEnvironment,
        *,
        mission_id: UUID | None = None,
        verification_run_ref: str | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> ProductEnvironment:
        async def _op(active: PostgresUnitOfWork) -> ProductEnvironment:
            current = await self._require(active, record.product_env_id)
            assert_transition(current.status, "IN_USE")
            now = self._clock.now()
            await self._repository.update_lifecycle(
                active.connection,
                current.product_env_id,
                status="IN_USE",
                updated_at=now,
            )
            await self._events.append(
                tenant_id=current.tenant_id,
                project_id=current.project_id,
                event_type="ProductEnvironmentInUse",
                aggregate_type="product_environment",
                aggregate_id=current.product_env_id,
                mission_id=mission_id or current.mission_id,
                payload={"verification_run_ref": verification_run_ref},
                uow=active,
            )
            return await self._require(active, current.product_env_id)

        return await self._run(uow, record.tenant_id, record.project_id, _op)

    # --- failure / teardown -------------------------------------------------

    async def record_failure(
        self,
        record: ProductEnvironment,
        *,
        reason: str,
        snapshot_ref: str | None = None,
        snapshot_bytes: bytes | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> ProductEnvironment:
        """FAILED from any pre-terminal state; the failure snapshot is
        recorded as an evidence-artifact reference with its content hash
        (retention/WORM wiring itself is Chapter 17.5, later stage)."""

        async def _op(active: PostgresUnitOfWork) -> ProductEnvironment:
            current = await self._require(active, record.product_env_id)
            assert_transition(current.status, "FAILED")
            snapshot: dict[str, object] | None = None
            if snapshot_ref is not None:
                digest = sha256_hex(snapshot_bytes or b"")
                snapshot = FailureSnapshot(
                    snapshot_ref=snapshot_ref,
                    content_hash=digest,
                    captured_at=self._clock.now(),
                ).model_dump(mode="json")
            now = self._clock.now()
            await self._repository.update_lifecycle(
                active.connection,
                current.product_env_id,
                status="FAILED",
                failure_snapshot=snapshot,
                updated_at=now,
            )
            await self._events.append(
                tenant_id=current.tenant_id,
                project_id=current.project_id,
                event_type="ProductEnvironmentFailed",
                aggregate_type="product_environment",
                aggregate_id=current.product_env_id,
                mission_id=current.mission_id,
                payload={"reason": reason, "snapshot": snapshot},
                uow=active,
            )
            return await self._require(active, current.product_env_id)

        return await self._run(uow, record.tenant_id, record.project_id, _op)

    async def teardown(
        self,
        record: ProductEnvironment,
        *,
        uow: PostgresUnitOfWork | None = None,
    ) -> ProductEnvironment:
        async def _op(active: PostgresUnitOfWork) -> ProductEnvironment:
            current = await self._require(active, record.product_env_id)
            assert_transition(current.status, "TEARDOWN")
            now = self._clock.now()
            await self._repository.update_lifecycle(
                active.connection,
                current.product_env_id,
                status="TEARDOWN",
                base_url=None,
                updated_at=now,
            )
            await self._events.append(
                tenant_id=current.tenant_id,
                project_id=current.project_id,
                event_type="ProductEnvironmentTornDown",
                aggregate_type="product_environment",
                aggregate_id=current.product_env_id,
                mission_id=current.mission_id,
                payload={},
                uow=active,
            )
            return await self._require(active, current.product_env_id)

        return await self._run(uow, record.tenant_id, record.project_id, _op)

    async def teardown_expired(
        self,
        *,
        now: datetime | None = None,
    ) -> list[ProductEnvironment]:
        """Destroy every expired ephemeral preview (Chapter 11.6's TTL rule).

        Each destroyed row is marked TEARDOWN through the ordinary
        tenant-scoped mutation path AND carries its own
        `ProductEnvironmentAbandoned` event — the observable signal feeding
        the abandoned-preview growth metric (distinct from an operator's
        ordinary `ProductEnvironmentTornDown` teardown). The sweep reads
        across tenants (system-level, mirroring the outbox dispatcher's
        posture).
        """
        moment = now or self._clock.now()
        expired = await self._expired(moment)
        destroyed: list[ProductEnvironment] = []
        for row in expired:
            torn = await self.teardown(row)
            await self._events.append(
                tenant_id=torn.tenant_id,
                project_id=torn.project_id,
                event_type="ProductEnvironmentAbandoned",
                aggregate_type="product_environment",
                aggregate_id=torn.product_env_id,
                mission_id=torn.mission_id,
                payload={
                    "reason": "ttl_expiry",
                    "ttl_expires_at": torn.ttl_expires_at.isoformat()
                    if torn.ttl_expires_at is not None
                    else None,
                    "class": torn.class_,
                },
                uow=None,
            )
            destroyed.append(torn)
        return destroyed

    async def _expired(self, now: datetime) -> list[ProductEnvironment]:
        from sqlalchemy import select

        from engine.product_env.tables import product_environments as pe_table

        results: list[ProductEnvironment] = []
        async with self._engine.connect() as connection:
            rows = await connection.execute(
                select(pe_table).where(
                    pe_table.c["class"] == EPHEMERAL_PREVIEW,
                    pe_table.c.ttl_expires_at.is_not(None),
                    pe_table.c.ttl_expires_at <= now,
                    pe_table.c.status.notin_(("TEARDOWN", "FAILED")),
                )
            )
            for row in rows.mappings().all():
                results.append(ProductEnvironment.model_validate(dict(row)))
        return results

    # --- reads --------------------------------------------------------------

    async def get_product_environment(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        product_env_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> ProductEnvironment:
        async def _op(active: PostgresUnitOfWork) -> ProductEnvironment:
            return await self._require(active, product_env_id)

        return await self._run(uow, tenant_id, project_id, _op)

    # --- helpers ------------------------------------------------------------

    async def _require(
        self, active: PostgresUnitOfWork, product_env_id: UUID
    ) -> ProductEnvironment:
        record = await self._repository.get_product_environment(
            active.connection, product_env_id
        )
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown ProductEnvironment")
        return record
