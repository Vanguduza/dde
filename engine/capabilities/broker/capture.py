"""Static-secret capture through the Credential Broker seam (Chapter 14.3).

Paste → hash → capture for OpenSandbox API keys. Metadata on
`captured_provider_credentials`; raw secret only in broker-private
`broker_static_secret_material`. Never logs the raw key.

Deferred: at-rest encryption of vault; live OpenSandbox provision wiring;
CredentialHandle issue from captured static secrets.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.broker.capture_hashing import (
    OPENSANDBOX_API_KEY_PROVIDER,
    capture_request_hash,
    secret_content_hash,
    secret_fingerprint,
    secret_last4,
)
from engine.capabilities.broker.capture_repository import CapturedCredentialRepository
from engine.contracts.captured_provider_credential import CapturedProviderCredential
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")
_MIN_SECRET_LEN = 8


@dataclass(frozen=True)
class CaptureResult:
    record: CapturedProviderCredential
    replayed: bool


class StaticSecretCaptureService:
    def __init__(
        self,
        engine: AsyncEngine,
        repository: CapturedCredentialRepository | None = None,
        events: EventService | None = None,
        commands: CommandLedger | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or CapturedCredentialRepository()
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
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

    async def capture_opensandbox_api_key(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        api_key: str,
        domain: str | None,
        captured_by: str,
        idempotency_key: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> CaptureResult:
        return await self.capture(
            tenant_id=tenant_id,
            project_id=project_id,
            provider_id=OPENSANDBOX_API_KEY_PROVIDER,
            secret=api_key,
            domain=domain,
            captured_by=captured_by,
            idempotency_key=idempotency_key,
            uow=uow,
        )

    async def capture(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        provider_id: str,
        secret: str,
        domain: str | None,
        captured_by: str,
        idempotency_key: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> CaptureResult:
        cleaned = secret.strip() if isinstance(secret, str) else ""
        if not cleaned or len(cleaned) < _MIN_SECRET_LEN:
            raise DdeError(
                "POLICY_DENIED",
                "API key is empty or too short to capture",
                details={"provider_id": provider_id, "min_length": _MIN_SECRET_LEN},
            )
        if not provider_id.strip():
            raise DdeError(
                "POLICY_DENIED",
                "provider_id is required to capture a static secret",
            )
        domain_clean = (
            domain.strip() if isinstance(domain, str) and domain.strip() else None
        )
        secret_hash = secret_content_hash(cleaned)
        fingerprint = secret_fingerprint(secret_hash)
        last4 = secret_last4(cleaned)
        request_hash = capture_request_hash(
            provider_id=provider_id,
            secret_hash=secret_hash,
            domain=domain_clean,
            captured_by=captured_by,
        )

        async def _op(active: PostgresUnitOfWork) -> CaptureResult:
            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                uow=active,
            )
            if not is_new:
                return self._replay(record)

            now = self._clock.now()
            prior = await self._repository.get_active_capture(
                active.connection,
                tenant_id=tenant_id,
                project_id=project_id,
                provider_id=provider_id,
            )
            if (
                prior is not None
                and prior.secret_hash == secret_hash
                and (prior.domain or None) == domain_clean
            ):
                await self._commands.complete(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    command_id=record.command_id,
                    result=self._public_payload(prior),
                    uow=active,
                )
                return CaptureResult(record=prior, replayed=True)

            capture_id = uuid7()
            new_record = CapturedProviderCredential(
                capture_id=capture_id,
                tenant_id=tenant_id,
                project_id=project_id,
                provider_id=provider_id,
                domain=domain_clean,
                secret_hash=secret_hash,
                fingerprint=fingerprint,
                last4=last4,
                status="CAPTURED",
                supersedes_capture_id=prior.capture_id if prior else None,
                superseded_by_capture_id=None,
                captured_by=captured_by,
                captured_at=now,
                revoked_at=None,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_capture(active.connection, new_record)
            await self._repository.insert_secret(
                active.connection,
                capture_id=capture_id,
                tenant_id=tenant_id,
                project_id=project_id,
                provider_id=provider_id,
                secret_value=cleaned,
                created_at=now,
            )
            if prior is not None:
                await self._repository.update_capture(
                    active.connection,
                    prior.capture_id,
                    status="SUPERSEDED",
                    superseded_by_capture_id=capture_id,
                    updated_at=now,
                )
                await self._repository.delete_secret(
                    active.connection, prior.capture_id
                )
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ProviderCredentialCaptured",
                aggregate_type="captured_provider_credential",
                aggregate_id=capture_id,
                payload={
                    "provider_id": provider_id,
                    "fingerprint": fingerprint,
                    "last4": last4,
                    "domain": domain_clean,
                    "supersedes_capture_id": (str(prior.capture_id) if prior else None),
                },
                uow=active,
            )
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=self._public_payload(new_record),
                uow=active,
            )
            return CaptureResult(record=new_record, replayed=False)

        return await self._run(uow, tenant_id, project_id, _op)

    async def inspect(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        provider_id: str = OPENSANDBOX_API_KEY_PROVIDER,
        uow: PostgresUnitOfWork | None = None,
    ) -> CapturedProviderCredential | None:
        async def _op(active: PostgresUnitOfWork) -> CapturedProviderCredential | None:
            return await self._repository.get_active_capture(
                active.connection,
                tenant_id=tenant_id,
                project_id=project_id,
                provider_id=provider_id,
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def resolve_secret(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        provider_id: str = OPENSANDBOX_API_KEY_PROVIDER,
        uow: PostgresUnitOfWork | None = None,
    ) -> str | None:
        """Broker-only reader. Never expose through Gateway/Studio."""

        async def _op(active: PostgresUnitOfWork) -> str | None:
            active_capture = await self._repository.get_active_capture(
                active.connection,
                tenant_id=tenant_id,
                project_id=project_id,
                provider_id=provider_id,
            )
            if active_capture is None:
                return None
            return await self._repository.read_secret(
                active.connection, active_capture.capture_id
            )

        return await self._run(uow, tenant_id, project_id, _op)

    def _replay(self, record: object) -> CaptureResult:
        status = getattr(record, "status", None)
        result = getattr(record, "result", None)
        if status != "completed" or not isinstance(result, dict):
            raise DdeError(
                "VERSION_CONFLICT",
                "Idempotent capture replay has no completed metadata result",
                details={"status": status},
            )
        captured = CapturedProviderCredential.model_validate(result)
        return CaptureResult(record=captured, replayed=True)

    @staticmethod
    def _public_payload(record: CapturedProviderCredential) -> dict[str, object]:
        return record.model_dump(mode="json")

    @staticmethod
    def public_status(record: CapturedProviderCredential) -> dict[str, object]:
        return {
            "capture_id": str(record.capture_id),
            "provider_id": record.provider_id,
            "domain": record.domain,
            "fingerprint": record.fingerprint,
            "last4": record.last4,
            "secret_hash": record.secret_hash,
            "status": record.status,
            "captured_at": record.captured_at.isoformat(),
            "captured": True,
        }
