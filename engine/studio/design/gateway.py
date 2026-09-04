"""DDE-069 DesignGateway.

Owns the design-session lifecycle and is the sole writer of
`design_sessions` and `design_artifacts`. It does not own project truth or
accepted design: an artifact is a proposal, and the only route from
proposal to accepted code runs Try live -> isolated candidate -> DDE-068
verification -> the promotion gate.

Three rules are enforced here rather than trusted:

*No substitution.* If no certified provider is available the request is
refused with a typed reason. There is no path that quietly produces
something else and calls it `/design`.

*Quarantine, not acceptance.* A provider that returns a malformed or
policy-failing artifact gets that artifact recorded as QUARANTINED with the
reason. It never becomes a candidate.

*Staleness is detectable.* A session records the design-system hash and PXG
revision its artifacts were generated against, so an artifact produced
under an older design system is refused at Try live rather than applied.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.design_artifact import DesignArtifact
from engine.contracts.design_session import DesignSession
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.candidates.service import CandidateService
from engine.studio.contract.service import FrontendContractService
from engine.studio.design.context import compile_context, design_system_snapshot
from engine.studio.design.providers import (
    DesignProviderRegistry,
    DesignProviderStatus,
    DesignRequest,
    ProviderArtifact,
    default_registry,
)
from engine.studio.pxg.service import PxgService, validate_key
from engine.studio.tables import design_artifacts, design_sessions
from engine.truth.db import open_unit_of_work

MAX_DIRECTIONS = 6

#: Neutral direction identities. Neutral on purpose: a label implying rank
#: would be a quality score with no evidence behind it (section 17.2).
DIRECTION_LABELS = ("A", "B", "C", "D", "E", "F")


@dataclass(frozen=True)
class DesignOutcome:
    session: DesignSession
    artifacts: tuple[DesignArtifact, ...]

    @property
    def usable(self) -> tuple[DesignArtifact, ...]:
        return tuple(item for item in self.artifacts if item.status != "QUARANTINED")


class DesignGateway:
    """Provider-neutral design-session lifecycle."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        registry: DesignProviderRegistry | None = None,
        pxg: PxgService | None = None,
        contracts: FrontendContractService | None = None,
        candidates: CandidateService | None = None,
    ) -> None:
        self._engine = engine
        self._registry = registry or default_registry()
        self._pxg = pxg or PxgService(engine)
        self._contracts = contracts or FrontendContractService(engine)
        self._candidates = candidates or CandidateService(engine, pxg=self._pxg)

    async def provider_statuses(self) -> tuple[DesignProviderStatus, ...]:
        """What the `/design` control renders. Never fabricated."""
        return await self._registry.statuses()

    async def request(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        scope_keys: list[str],
        instruction: str,
        provider_id: str = "claude-design",
        direction_count: int = 3,
        mission_id: UUID | None = None,
        conversation_id: UUID | None = None,
    ) -> DesignOutcome:
        """Open a session and ask a certified provider for directions."""
        if not 1 <= direction_count <= MAX_DIRECTIONS:
            raise DdeError(
                "VALIDATION_FAILED",
                f"direction_count must be between 1 and {MAX_DIRECTIONS}",
                retryable=False,
                details={"direction_count": direction_count},
            )
        for key in scope_keys:
            validate_key(key)

        # Resolve the provider *before* compiling context: there is no
        # reason to assemble an export payload for a call that cannot
        # happen, and a refusal here never touches project state.
        provider = await self._registry.resolve(provider_id)

        graph = await self._pxg.load(tenant_id=tenant_id, project_id=project_id)
        contract = await self._contracts.get_active(
            tenant_id=tenant_id, project_id=project_id
        )
        snapshot = design_system_snapshot()
        context = compile_context(
            scope_keys=scope_keys,
            graph=graph,
            contract=contract,
            design_system=snapshot,
        )

        now = datetime.now(UTC)
        session = DesignSession(
            session_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            conversation_id=conversation_id,
            candidate_id=None,
            status="OPEN",
            scope_keys=list(scope_keys),
            design_system_hash=snapshot.content_hash,
            base_pxg_revision=graph.revision,
            context_manifest=context.manifest,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                design_sessions.insert().values(
                    **session.model_dump(exclude={"scope_keys", "context_manifest"}),
                    scope_keys=list(scope_keys),
                    context_manifest=context.manifest,
                )
            )
            await uow.commit()

        produced = await provider.generate(
            DesignRequest(
                context=context,
                direction_count=direction_count,
                instruction=instruction,
            )
        )
        artifacts = await self._record(
            tenant_id=tenant_id,
            project_id=project_id,
            session=session,
            produced=produced,
            provider_id=provider_id,
            design_system_hash=snapshot.content_hash,
        )
        return DesignOutcome(session=session, artifacts=artifacts)

    async def _record(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        session: DesignSession,
        produced: tuple[ProviderArtifact, ...],
        provider_id: str,
        design_system_hash: str,
    ) -> tuple[DesignArtifact, ...]:
        now = datetime.now(UTC)
        records: list[DesignArtifact] = []
        for index, item in enumerate(produced):
            quarantine = _quarantine_reason(item, design_system_hash)
            payload = json.dumps(item.content, sort_keys=True, default=str)
            records.append(
                DesignArtifact(
                    artifact_id=uuid7(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    session_id=session.session_id,
                    direction_label=item.direction_label
                    or DIRECTION_LABELS[index % len(DIRECTION_LABELS)],
                    revision=1,
                    status="QUARANTINED" if quarantine else "GENERATED",
                    provider_id=provider_id,
                    content_hash=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                    content=item.content,
                    provenance={
                        "provider_id": provider_id,
                        "provider_version": item.provider_version,
                        "design_system_hash": design_system_hash,
                        "base_pxg_revision": session.base_pxg_revision,
                        "retrieved_at": now.isoformat(),
                    },
                    quarantine_reason=quarantine,
                    candidate_id=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            for record in records:
                await uow.connection.execute(
                    design_artifacts.insert().values(
                        **record.model_dump(exclude={"content", "provenance"}),
                        content=record.content,
                        provenance=record.provenance,
                    )
                )
            await uow.commit()
        return tuple(records)

    async def try_live(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        artifact_id: UUID,
        mission_id: UUID | None = None,
    ) -> tuple[DesignArtifact, UUID]:
        """Turn a design direction into an isolated candidate.

        This is the only route from artifact to code, and it refuses a
        quarantined artifact and a stale session outright. A design
        artifact never becomes accepted state by this call: it becomes a
        candidate, which still has to pass the promotion gate.
        """
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(design_artifacts).where(
                    design_artifacts.c.artifact_id == artifact_id,
                    design_artifacts.c.tenant_id == tenant_id,
                    design_artifacts.c.project_id == project_id,
                )
            )
            row = result.mappings().first()
            if row is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "unknown design artifact in this project",
                    retryable=False,
                    details={"artifact_id": str(artifact_id)},
                )
            artifact = DesignArtifact.model_validate(dict(row))

            session_row = (
                (
                    await uow.connection.execute(
                        select(design_sessions).where(
                            design_sessions.c.session_id == artifact.session_id
                        )
                    )
                )
                .mappings()
                .first()
            )
            if session_row is None:
                raise DdeError(
                    "CONTEXT_INCOMPLETE",
                    "the artifact's design session is missing; its staleness "
                    "cannot be checked, so it may not be tried live",
                    retryable=False,
                    details={"artifact_id": str(artifact_id)},
                )
            session = DesignSession.model_validate(dict(session_row))

        if artifact.status == "QUARANTINED":
            raise DdeError(
                "DESIGN_SOURCE_REJECTED",
                "a quarantined artifact cannot become a candidate",
                retryable=False,
                details={
                    "artifact_id": str(artifact_id),
                    "reason": artifact.quarantine_reason,
                },
            )
        if artifact.status == "TRIED_LIVE":
            raise DdeError(
                "POLICY_DENIED",
                "this artifact already has a candidate",
                retryable=False,
                details={
                    "artifact_id": str(artifact_id),
                    "candidate_id": str(artifact.candidate_id),
                },
            )

        current_hash = design_system_snapshot().content_hash
        if session.design_system_hash != current_hash:
            raise DdeError(
                "STALE_REVISION",
                "the project design system changed after this artifact was "
                "generated; regenerate before trying it live",
                retryable=False,
                details={
                    "artifact_id": str(artifact_id),
                    "generated_against": session.design_system_hash,
                    "current": current_hash,
                },
            )

        candidate = await self._candidates.create(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id or session.mission_id,
            title=f"Direction {artifact.direction_label}",
            origin="DESIGN_ARTIFACT",
            scope_keys=list(session.scope_keys),
            provenance={
                "design_artifact_id": str(artifact.artifact_id),
                "design_session_id": str(session.session_id),
                "provider_id": artifact.provider_id,
                "design_system_hash": session.design_system_hash,
            },
        )

        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                update(design_artifacts)
                .where(design_artifacts.c.artifact_id == artifact_id)
                .values(
                    status="TRIED_LIVE",
                    candidate_id=candidate.candidate_id,
                    updated_at=now,
                )
            )
            await uow.commit()
        return artifact, candidate.candidate_id

    async def artifacts_for(
        self, *, tenant_id: UUID, project_id: UUID, session_id: UUID
    ) -> tuple[DesignArtifact, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(design_artifacts)
                .where(
                    design_artifacts.c.session_id == session_id,
                    design_artifacts.c.tenant_id == tenant_id,
                    design_artifacts.c.project_id == project_id,
                )
                .order_by(design_artifacts.c.direction_label)
            )
            rows = result.mappings().all()
        return tuple(DesignArtifact.model_validate(dict(row)) for row in rows)


def _quarantine_reason(
    artifact: ProviderArtifact, design_system_hash: str
) -> str | None:
    """Reject a malformed or off-system artifact before it can be tried.

    A provider returning nonsense is a provider failure, recorded as one.
    Letting it through and discovering the problem at build time would
    make the failure look like DDE's.
    """
    del design_system_hash
    if not isinstance(artifact.content, dict) or not artifact.content:
        return "provider returned an empty or non-object artifact"
    if not artifact.direction_label:
        return "provider returned an artifact with no direction label"
    nodes = artifact.content.get("nodes")
    if nodes is not None and not isinstance(nodes, list):
        return "artifact 'nodes' must be a list"
    return None
