"""EDR-0019 Epic C discovery runtime.

A candidate carries no Project Truth, implementation, execution or capability
authority. Qualification may cap authority downwards and may never raise it, and
no method here writes `source_trust` from a trial outcome.

The admission bridge deliberately stops at `SourceRecord`. A `SourceAdmission`
requires an acquired, hashed artifact, which is the EDR-0018 acquisition
pipeline's responsibility; discovery hands a qualified source over to it rather
than fabricating an admission without content.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.contracts.discovery_candidate import DiscoveryCandidate
from engine.contracts.discovery_observation import DiscoveryObservation
from engine.contracts.discovery_qualification import DiscoveryQualification
from engine.contracts.discovery_transition import DiscoveryTransition
from engine.contracts.discovery_trial import DiscoveryTrial
from engine.contracts.graph_trust_projection import GraphTrustProjection
from engine.contracts.source_record import SourceRecord
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.source.discovery import policy
from engine.source.discovery.identity import candidate_id_for, normalize_locator
from engine.source.discovery.repository import DiscoveryRepository
from engine.source.repository import SourceRepository
from engine.truth.db import open_unit_of_work

DISCOVERY_POLICY_REVISION = "dde-discovery-v1"

_DOMAIN_BY_SCHEME = {
    "GITHUB_REPOSITORY": "REPOSITORY",
    "PACKAGE_COORDINATE": "PACKAGE",
    "HTTP_ORIGIN_PATH": "DOCUMENTATION",
    "OPAQUE": "OTHER",
}
_BLOCKING_SANITIZER_CLASSES = frozenset(
    {"SECRET", "PROMPT_INJECTION", "MALICIOUS_PAYLOAD"}
)


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


class DiscoveryService:
    """Open-world discovery over the domain-neutral Source Intelligence base."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        repository: DiscoveryRepository | None = None,
        sources: SourceRepository | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or DiscoveryRepository()
        self._sources = sources or SourceRepository()

    # ---------------------------------------------------------------- observe

    async def observe(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        locator: str,
        discovered_by: str,
        observed_via: str,
        observer_ref: str | None = None,
        title: str | None = None,
        publisher: str | None = None,
        content_hash: str | None = None,
    ) -> DiscoveryCandidate:
        """Create or merge a candidate, then append the sighting as evidence."""
        scheme, key = normalize_locator(locator)
        candidate_id = candidate_id_for(project_id, key)
        host = urlsplit(locator if "://" in locator else f"https://{locator}").netloc
        now = _now()

        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            existing = await self._repository.get_candidate(
                uow.connection, candidate_id=candidate_id
            )
            if existing is None:
                candidate = DiscoveryCandidate(
                    candidate_id=candidate_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    canonical_locator=locator,
                    normalized_identity_key=key,
                    identity_scheme=scheme,
                    title=title,
                    publisher=publisher,
                    lifecycle_state="DISCOVERED",
                    source_trust=policy.assign_trust(
                        identity_scheme=scheme, host=host.split(":")[0]
                    ),
                    discovered_by=discovered_by,
                    discovery_refs=[observer_ref] if observer_ref else [],
                    observation_count=1,
                    license_ids=[],
                    content_hash=content_hash,
                    sanitizer_findings=[],
                    architecture_findings=[],
                    first_seen_at=now,
                    last_observed_at=now,
                    created_at=now,
                    updated_at=now,
                )
                await self._repository.insert_candidate(
                    uow.connection, candidate=candidate
                )
                await self._append_transition(
                    uow.connection,
                    candidate=candidate,
                    from_state=None,
                    to_state="DISCOVERED",
                    reason_code="discovery.first_sighting",
                    actor="SYSTEM",
                )
            else:
                refs = list(existing.discovery_refs)
                if observer_ref and observer_ref not in refs:
                    refs.append(observer_ref)
                candidate = existing.model_copy(
                    update={
                        "observation_count": existing.observation_count + 1,
                        "discovery_refs": refs,
                        "title": existing.title or title,
                        "publisher": existing.publisher or publisher,
                        "content_hash": existing.content_hash or content_hash,
                        "last_observed_at": now,
                        "updated_at": now,
                    }
                )
                await self._repository.update_candidate(
                    uow.connection, candidate=candidate
                )

            await self._repository.insert_observation(
                uow.connection,
                observation=DiscoveryObservation(
                    observation_id=uuid7(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    candidate_id=candidate_id,
                    observed_via=observed_via,
                    observer_ref=observer_ref,
                    content_hash=content_hash,
                    observed_at=now,
                    created_at=now,
                ),
            )
            await uow.commit()
        return candidate

    # ------------------------------------------------------------- lifecycle

    async def _append_transition(
        self,
        connection: AsyncConnection,
        *,
        candidate: DiscoveryCandidate,
        from_state: str | None,
        to_state: str,
        reason_code: str,
        actor: str,
        evidence_pointer: str | None = None,
    ) -> None:
        policy.require_legal_transition(from_state, to_state)
        sequence = await self._repository.next_sequence(
            connection,
            candidate_id=candidate.candidate_id,
        )
        now = _now()
        await self._repository.append_transition(
            connection,
            transition=DiscoveryTransition(
                transition_id=uuid7(),
                tenant_id=candidate.tenant_id,
                project_id=candidate.project_id,
                candidate_id=candidate.candidate_id,
                sequence=sequence,
                from_state=from_state,
                to_state=to_state,
                reason_code=reason_code,
                actor=actor,
                evidence_pointer=evidence_pointer,
                decision_hash=_hash(
                    {
                        "candidate": str(candidate.candidate_id),
                        "sequence": sequence,
                        "from": from_state,
                        "to": to_state,
                        "reason": reason_code,
                    }
                ),
                occurred_at=now,
                created_at=now,
            ),
        )

    async def advance(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        to_state: str,
        reason_code: str,
        actor: str = "SYSTEM",
        evidence_pointer: str | None = None,
        sanitizer_findings: list[dict[str, object]] | None = None,
        architecture_findings: list[dict[str, object]] | None = None,
    ) -> DiscoveryCandidate:
        """Move a candidate one legal step, appending immutable history."""
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            candidate = await self._require_candidate(uow.connection, candidate_id)
            await self._append_transition(
                uow.connection,
                candidate=candidate,
                from_state=candidate.lifecycle_state,
                to_state=to_state,
                reason_code=reason_code,
                actor=actor,
                evidence_pointer=evidence_pointer,
            )
            updates: dict[str, object] = {
                "lifecycle_state": to_state,
                "updated_at": _now(),
            }
            if sanitizer_findings is not None:
                updates["sanitizer_findings"] = sanitizer_findings
            if architecture_findings is not None:
                updates["architecture_findings"] = architecture_findings
            candidate = candidate.model_copy(update=updates)
            await self._repository.update_candidate(uow.connection, candidate=candidate)
            await uow.commit()
        return candidate

    async def sanitize(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        findings: list[dict[str, object]],
    ) -> DiscoveryCandidate:
        """Record sanitizer findings; a blocking class rejects rather than advances."""
        blocking = [
            finding
            for finding in findings
            if str(finding.get("finding_class")) in _BLOCKING_SANITIZER_CLASSES
        ]
        if blocking:
            return await self.advance(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
                to_state="REJECTED",
                reason_code="discovery.sanitizer_blocking_finding",
                sanitizer_findings=findings,
            )
        return await self.advance(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
            to_state="SANITIZED",
            reason_code="discovery.sanitized",
            sanitizer_findings=findings,
        )

    # ----------------------------------------------------------------- trials

    async def open_trial(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        trial_kind: str,
        sandbox_profile: str,
        command: list[str],
        network_scopes: list[str] | None = None,
        filesystem_scopes: list[str] | None = None,
        capability_lease_id: UUID | None = None,
    ) -> DiscoveryTrial:
        now = _now()
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            candidate = await self._require_candidate(uow.connection, candidate_id)
            if candidate.lifecycle_state != "TRIAL_ELIGIBLE":
                raise DdeError(
                    "POLICY_DENIED",
                    "a discovery trial requires a TRIAL_ELIGIBLE candidate",
                    retryable=False,
                    details={"lifecycle_state": candidate.lifecycle_state},
                )
            trial = DiscoveryTrial(
                trial_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
                trial_kind=trial_kind,
                sandbox_profile=sandbox_profile,
                declared_network_scopes=list(network_scopes or []),
                declared_filesystem_scopes=list(filesystem_scopes or []),
                capability_lease_id=capability_lease_id,
                command=list(command),
                outcome="PENDING",
                observed_signals=[],
                started_at=now,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_trial(uow.connection, trial=trial)
            await uow.commit()
        return trial

    async def complete_trial(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        trial: DiscoveryTrial,
        outcome: str,
        observed_signals: list[dict[str, object]] | None = None,
        evidence_pointer: str | None = None,
    ) -> DiscoveryCandidate:
        """Close a trial and advance lifecycle only. Trust is never touched here."""
        now = _now()
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            closed = trial.model_copy(
                update={
                    "outcome": outcome,
                    "observed_signals": list(observed_signals or []),
                    "evidence_pointer": evidence_pointer,
                    "completed_at": now,
                    "updated_at": now,
                }
            )
            await self._repository.update_trial(uow.connection, trial=closed)
            candidate = await self._require_candidate(
                uow.connection, trial.candidate_id
            )
            to_state = "SANDBOX_TESTED" if outcome == "PASSED" else "REJECTED"
            await self._append_transition(
                uow.connection,
                candidate=candidate,
                from_state=candidate.lifecycle_state,
                to_state=to_state,
                reason_code=f"discovery.trial_{outcome.lower()}",
                actor="VERIFIER",
                evidence_pointer=evidence_pointer,
            )
            # source_trust is intentionally absent from this update: a passing
            # sandbox trial is lifecycle evidence and never authority.
            candidate = candidate.model_copy(
                update={"lifecycle_state": to_state, "updated_at": now}
            )
            await self._repository.update_candidate(uow.connection, candidate=candidate)
            await uow.commit()
        return candidate

    # ---------------------------------------------------------- qualification

    async def qualify(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        disposition: str,
        rationale: str,
        requested_ceiling: str | None = None,
        trial_id: UUID | None = None,
        hold_expires_at: datetime | None = None,
    ) -> tuple[DiscoveryQualification, DiscoveryCandidate]:
        """Qualify a candidate into a bounded disposition and authority ceiling."""
        polarity, allowed, forbidden = policy.disposition_rule(disposition)
        now = _now()
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            candidate = await self._require_candidate(uow.connection, candidate_id)
            ceiling = policy.cap_authority(
                candidate.source_trust, requested_ceiling or candidate.source_trust
            )
            qualification = DiscoveryQualification(
                qualification_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
                disposition=disposition,
                authority_ceiling=ceiling,
                allowed_uses=list(allowed),
                forbidden_uses=list(forbidden),
                guidance_polarity=polarity,
                rationale=rationale,
                policy_revision=DISCOVERY_POLICY_REVISION,
                trial_id=trial_id,
                hold_expires_at=hold_expires_at,
                qualified_at=now,
                created_at=now,
                updated_at=now,
            )
            await self._repository.insert_qualification(
                uow.connection, qualification=qualification
            )

            terminal = policy.terminal_state_for(disposition)
            if candidate.lifecycle_state != "QUALIFIED" and terminal != "REJECTED":
                await self._append_transition(
                    uow.connection,
                    candidate=candidate,
                    from_state=candidate.lifecycle_state,
                    to_state="QUALIFIED",
                    reason_code=f"discovery.qualified.{disposition.lower()}",
                    actor="POLICY",
                )
                candidate = candidate.model_copy(
                    update={"lifecycle_state": "QUALIFIED", "updated_at": now}
                )
            if terminal != "QUALIFIED":
                await self._append_transition(
                    uow.connection,
                    candidate=candidate,
                    from_state=candidate.lifecycle_state,
                    to_state=terminal,
                    reason_code=f"discovery.disposition.{disposition.lower()}",
                    actor="POLICY",
                )
                candidate = candidate.model_copy(
                    update={"lifecycle_state": terminal, "updated_at": now}
                )

            if policy.admits(disposition):
                source = await self._bridge_source_record(
                    uow.connection, candidate=candidate, ceiling=ceiling
                )
                candidate = candidate.model_copy(update={"source_id": source.source_id})

            await self._repository.update_candidate(uow.connection, candidate=candidate)
            await self._repository.insert_projection(
                uow.connection,
                projection=GraphTrustProjection(
                    projection_id=uuid7(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    candidate_id=candidate_id,
                    subject_kind="DISCOVERY_CANDIDATE",
                    projected_trust=candidate.source_trust,
                    authority_ceiling=ceiling,
                    allowed_uses=list(allowed),
                    forbidden_uses=list(forbidden),
                    guidance_polarity=polarity,
                    graph_revision=DISCOVERY_POLICY_REVISION,
                    projection_hash=_hash(
                        {
                            "candidate": str(candidate_id),
                            "ceiling": ceiling,
                            "polarity": polarity,
                        }
                    ),
                    retrievable=policy.admits(disposition),
                    satisfies_positive_slots=(
                        polarity == "POSITIVE" and policy.admits(disposition)
                    ),
                    projected_at=now,
                    created_at=now,
                    updated_at=now,
                ),
            )
            await uow.commit()
        return qualification, candidate

    async def _bridge_source_record(
        self,
        connection: AsyncConnection,
        *,
        candidate: DiscoveryCandidate,
        ceiling: str,
    ) -> SourceRecord:
        now = _now()
        source = SourceRecord(
            source_id=uuid7(),
            tenant_id=candidate.tenant_id,
            project_id=candidate.project_id,
            provider_key=candidate.normalized_identity_key,
            display_name=candidate.title or candidate.normalized_identity_key,
            source_domain=_DOMAIN_BY_SCHEME.get(candidate.identity_scheme, "OTHER"),
            source_class="OPEN_WORLD_DISCOVERY",
            source_kind=candidate.identity_scheme,
            source_trust=ceiling,
            status="AVAILABLE",
            policy_revision=DISCOVERY_POLICY_REVISION,
            config={"canonical_locator": candidate.canonical_locator},
            created_at=now,
            updated_at=now,
        )
        await self._sources.upsert_source(connection, source)
        return source

    async def _require_candidate(
        self, connection: AsyncConnection, candidate_id: UUID
    ) -> DiscoveryCandidate:
        candidate = await self._repository.get_candidate(
            connection,
            candidate_id=candidate_id,
        )
        if candidate is None:
            raise DdeError(
                "NOT_FOUND",
                "discovery candidate not found",
                retryable=False,
                details={"candidate_id": str(candidate_id)},
            )
        return candidate
