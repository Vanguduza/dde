"""Production donor-search fan-out (DDE-066 / EDR-0015 / Ch.12.4).

`DonorDiscoveryService.search` is the mutation call site: allowlist,
broker-issued credential, query quota, `ExternalEffectService.prepare`
then `mark_sent` BEFORE the injected GET, classify-before-use grouping,
DDE-046 pins in the same inventory, taint persist via DonorLab ingest.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.broker.service import CredentialBrokerService
from engine.capabilities.lease_service import CapabilityLeaseService
from engine.capabilities.seed import side_effect_class_for
from engine.contracts.worker_run import WorkerRun
from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex
from engine.donor.allowlist import assert_uri_admitted
from engine.donor.grouping import (
    Classifier,
    DiscoveryHit,
    FeatureCategory,
    GroupedDonorResults,
    group_discovery_hits,
    grouped_results_as_dict,
    grouped_results_from_dict,
)
from engine.donor.quota import assert_donor_search_quota, resolve_donor_search_ceiling
from engine.donor.repository import DonorRepository
from engine.donor.service import DonorLabService
from engine.events.idempotency import CommandLedger
from engine.execution.service import ExecutionPlanService
from engine.recovery.hashing import effect_response_hash
from engine.recovery.scope import DONOR_SEARCH_GET_OPERATION, DONOR_SEARCH_SYSTEM
from engine.recovery.service import ExternalEffectService
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

CAPABILITY_DONOR_DISCOVERY = "capability.donor_discovery"
COMMAND_TYPE = "frontend.donors.run_discovery"
AuthFetchFn = Callable[[str, str | None], str]

T = TypeVar("T")


@dataclass(frozen=True)
class SearchQuery:
    uri: str
    feature_ids: tuple[str, ...] = ()


def parse_search_body(
    uri: str, body: str, feature_ids: tuple[str, ...]
) -> tuple[DiscoveryHit, ...]:
    """Turn one allowlisted GET body into classified-later hits."""
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return (
            DiscoveryHit(
                source_uri=uri, summary=body[:4000], feature_hints=feature_ids
            ),
        )
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        hits: list[DiscoveryHit] = []
        for item in payload["items"]:
            if not isinstance(item, dict):
                continue
            source = str(
                item.get("html_url") or item.get("url") or item.get("source_uri") or ""
            )
            if not source:
                continue
            licence = item.get("license")
            spdx = ""
            if isinstance(licence, dict):
                spdx = str(licence.get("spdx_id") or "")
            summary = " ".join(
                part for part in (str(item.get("description") or ""), spdx) if part
            )
            hits.append(
                DiscoveryHit(
                    source_uri=source,
                    summary=summary,
                    feature_hints=feature_ids,
                )
            )
        return tuple(hits)
    summary = body[:4000]
    if isinstance(payload, dict):
        name = payload.get("name") or payload.get("description")
        if name is not None:
            summary = str(name)
    return (DiscoveryHit(source_uri=uri, summary=summary, feature_hints=feature_ids),)


class DonorDiscoveryService:
    """Control-plane capability.donor_discovery — not a T2 worker sandbox."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        effects: ExternalEffectService | None = None,
        leases: CapabilityLeaseService | None = None,
        broker: CredentialBrokerService | None = None,
        plans: ExecutionPlanService | None = None,
        commands: CommandLedger | None = None,
        ingest: DonorLabService | None = None,
        repository: DonorRepository | None = None,
        fetch: AuthFetchFn | None = None,
    ) -> None:
        self._engine = engine
        self._effects = effects or ExternalEffectService(engine)
        self._leases = leases or CapabilityLeaseService(engine)
        self._broker = broker or CredentialBrokerService(engine)
        self._plans = plans or ExecutionPlanService(engine)
        self._commands = commands or CommandLedger(engine)
        self._ingest = ingest or DonorLabService(engine)
        self._repository = repository or DonorRepository()
        self._fetch = fetch

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
            outcome = await body(owned)
            await owned.commit()
            return outcome

    async def search(
        self,
        *,
        worker_run: WorkerRun,
        prd_id: str,
        features: tuple[FeatureCategory, ...],
        queries: tuple[SearchQuery, ...],
        idempotency_key: str,
        classifier: Classifier | None = None,
        fetch: AuthFetchFn | None = None,
    ) -> GroupedDonorResults:
        """Fan-out + classify + pin merge. Production mutation for DDE-066."""
        tenant_id = worker_run.tenant_id
        project_id = worker_run.project_id
        request_hash = sha256_hex(
            (
                f"{COMMAND_TYPE}|{prd_id}|{worker_run.run_id}|"
                f"{tuple(item.uri for item in queries)}|"
                f"{tuple(item.feature_id for item in features)}"
            ).encode()
        )
        record, is_new = await self._commands.begin(
            tenant_id=tenant_id,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if not is_new:
            return self._replay(record)

        try:
            results = await self._search_new(
                worker_run=worker_run,
                prd_id=prd_id,
                features=features,
                queries=queries,
                idempotency_key=idempotency_key,
                classifier=classifier,
                fetch=fetch,
            )
        except Exception as exc:
            await self._commands.fail(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result={"error": type(exc).__name__},
            )
            raise

        await self._commands.complete(
            tenant_id=tenant_id,
            project_id=project_id,
            command_id=record.command_id,
            result=grouped_results_as_dict(results),
        )
        return results

    def _replay(self, record: object) -> GroupedDonorResults:
        status = getattr(record, "status", None)
        stored = getattr(record, "result", None)
        if status == "completed" and isinstance(stored, dict):
            return grouped_results_from_dict(stored)
        if status == "in_progress":
            raise DdeError(
                "VERSION_CONFLICT",
                "Donor discovery command still in progress",
                retryable=True,
                details={"idempotency_key": getattr(record, "idempotency_key", None)},
            )
        raise DdeError(
            "POLICY_DENIED",
            "Donor discovery idempotency key is not replayable",
            retryable=False,
            details={"idempotency_key": getattr(record, "idempotency_key", None)},
        )

    async def _search_new(
        self,
        *,
        worker_run: WorkerRun,
        prd_id: str,
        features: tuple[FeatureCategory, ...],
        queries: tuple[SearchQuery, ...],
        idempotency_key: str,
        classifier: Classifier | None,
        fetch: AuthFetchFn | None,
    ) -> GroupedDonorResults:
        tenant_id = worker_run.tenant_id
        project_id = worker_run.project_id
        plan = await self._plans.get_plan(
            tenant_id=tenant_id,
            project_id=project_id,
            plan_id=worker_run.execution_plan_id,
        )
        existing = await self._effects.list_for_run(
            tenant_id=tenant_id,
            project_id=project_id,
            worker_run_id=worker_run.run_id,
        )
        already = sum(
            1
            for row in existing
            if row.target_system == DONOR_SEARCH_SYSTEM
            and row.operation == DONOR_SEARCH_GET_OPERATION
        )
        assert_donor_search_quota(
            ceiling=resolve_donor_search_ceiling(plan.token_budget),
            requested=len(queries),
            already=already,
        )

        lease = await self._leases.request(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=worker_run.mission_id,
            task_id=plan.task_id,
            execution_plan_id=plan.plan_id,
            worker_run_id=worker_run.run_id,
            environment_id=worker_run.environment_id,
            capability_id=CAPABILITY_DONOR_DISCOVERY,
            capability_version="1",
            requested_by="engine.donor.discovery_service.DonorDiscoveryService",
            idempotency_key=f"{idempotency_key}:lease:{CAPABILITY_DONOR_DISCOVERY}",
        )
        if lease.status == "DENIED":
            raise DdeError(
                "POLICY_DENIED",
                "capability.donor_discovery lease denied",
                retryable=False,
                details={"lease_id": str(lease.lease_id)},
            )
        active_lease = await self._leases.require_active(
            tenant_id=tenant_id,
            project_id=project_id,
            worker_run_id=worker_run.run_id,
            capability_id=CAPABILITY_DONOR_DISCOVERY,
        )
        issued = await self._broker.issue(
            tenant_id=tenant_id,
            project_id=project_id,
            lease_id=active_lease.lease_id,
            requested_by="engine.donor.discovery_service.DonorDiscoveryService",
            idempotency_key=f"{idempotency_key}:broker:{active_lease.lease_id}",
        )
        secret = issued.secret_value
        if secret is None:
            raise DdeError(
                "POLICY_DENIED",
                "broker did not mint a one-time donor-search credential",
                retryable=False,
                details={"handle_id": str(issued.handle.handle_id)},
            )
        transport = fetch or self._fetch or _default_fetch
        hits: list[DiscoveryHit] = []
        try:
            for query in queries:
                body = await self._journaled_get(
                    worker_run=worker_run,
                    lease_id=active_lease.lease_id,
                    uri=query.uri,
                    idempotency_key=f"{idempotency_key}:GET:{query.uri}",
                    secret=secret,
                    transport=transport,
                )
                hits.extend(parse_search_body(query.uri, body, query.feature_ids))
        finally:
            del secret

        hits.extend(await self._pin_hits(tenant_id=tenant_id, project_id=project_id))
        results = group_discovery_hits(
            prd_id=prd_id,
            features=features,
            hits=tuple(hits),
            classifier=classifier,
        )
        if "classifier_unreachable" not in results.refusals:
            await self._persist_search_hits(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=worker_run.mission_id,
                idempotency_key=idempotency_key,
                hits=tuple(hit for hit in hits if not hit.pin),
            )
        return results

    async def _journaled_get(
        self,
        *,
        worker_run: WorkerRun,
        lease_id: UUID,
        uri: str,
        idempotency_key: str,
        secret: str,
        transport: AuthFetchFn,
    ) -> str:
        assert_uri_admitted(uri)
        effect = await self._effects.prepare(
            tenant_id=worker_run.tenant_id,
            project_id=worker_run.project_id,
            mission_id=worker_run.mission_id,
            worker_run_id=worker_run.run_id,
            capability_lease_id=lease_id,
            target_system=DONOR_SEARCH_SYSTEM,
            target_resource=uri,
            operation=DONOR_SEARCH_GET_OPERATION,
            side_effect_class=side_effect_class_for(CAPABILITY_DONOR_DISCOVERY),
            idempotency_key=idempotency_key,
            evidence_ref=uri,
        )
        if effect.status != "PREPARED":
            raise DdeError(
                "VERSION_CONFLICT",
                "donor-search GET already journaled for this key — refusing "
                "a second fetch",
                retryable=False,
                details={"effect_id": str(effect.effect_id), "status": effect.status},
            )
        await self._effects.mark_sent(
            tenant_id=worker_run.tenant_id,
            project_id=worker_run.project_id,
            effect_id=effect.effect_id,
        )
        try:
            body = transport(uri, secret)
        except TimeoutError as exc:
            await self._effects.mark_unknown(
                tenant_id=worker_run.tenant_id,
                project_id=worker_run.project_id,
                effect_id=effect.effect_id,
                reason=str(exc),
            )
            raise
        except Exception as exc:
            await self._effects.mark_failed(
                tenant_id=worker_run.tenant_id,
                project_id=worker_run.project_id,
                effect_id=effect.effect_id,
                reason=str(exc),
            )
            raise
        await self._effects.mark_confirmed(
            tenant_id=worker_run.tenant_id,
            project_id=worker_run.project_id,
            effect_id=effect.effect_id,
            external_reference=uri,
            response_hash=effect_response_hash(
                {"uri": uri, "bytes": len(body.encode())}
            ),
        )
        return body

    async def _pin_hits(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> tuple[DiscoveryHit, ...]:
        async def _op(active: PostgresUnitOfWork) -> tuple[DiscoveryHit, ...]:
            artifacts = await self._repository.list_artifacts_for_project(
                active.connection, project_id=project_id
            )
            return tuple(
                DiscoveryHit(
                    source_uri=item.source_uri,
                    summary=item.source_class,
                    feature_hints=(),
                    pin=True,
                )
                for item in artifacts
            )

        result = await self._run(None, tenant_id, project_id, _op)
        return result

    async def _persist_search_hits(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        idempotency_key: str,
        hits: tuple[DiscoveryHit, ...],
    ) -> None:
        seen: set[str] = set()
        for hit in hits:
            if hit.source_uri in seen:
                continue
            seen.add(hit.source_uri)
            await self._ingest.submit_uri(
                tenant_id=tenant_id,
                project_id=project_id,
                source_uri=hit.source_uri,
                idempotency_key=f"{idempotency_key}:ingest:{hit.source_uri}",
                content=(hit.summary or hit.source_uri).encode(),
                media_kind="readme",
                mission_id=mission_id,
            )


def _default_fetch(uri: str, authorization: str | None) -> str:
    from adapters.donor.http import fetch_uri

    return fetch_uri(uri, authorization=authorization)
