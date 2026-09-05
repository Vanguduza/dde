"""DDE-069 candidate verification scheduling over the existing DDE-068 bindings.

This module owns request state only. It never writes VerificationRun or Evidence
rows and never decides PASS/FAIL. A LIVE candidate preview can request the
already-bound DDE-068 checks; the verification subsystem remains the sole owner
of the eventual run and verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_preview_session import FrontendPreviewSession
from engine.contracts.frontend_verification_request import FrontendVerificationRequest
from engine.core.ids import uuid7
from engine.studio.mutations.executor import MutationExecutor
from engine.studio.preview_runtime.service import PreviewState
from engine.studio.pxg.service import PxgGraph
from engine.studio.tables import frontend_verification_requests
from engine.truth.db import open_unit_of_work
from engine.verification.repository import AcceptanceOracleRepository


@dataclass(frozen=True)
class VerificationBinding:
    task_id: UUID | None
    acceptance_oracle_version: str | None
    required_kinds: tuple[str, ...]
    state: str
    reason: str | None


def derive_verification_binding(
    graph: PxgGraph, screen_key: str
) -> VerificationBinding:
    screen = graph.node_by_key(screen_key)
    if screen is None or screen.node_kind != "screen":
        return VerificationBinding(
            None, None, (), "BLOCKED", "preview screen is absent from the candidate PXG"
        )
    raw_kinds = screen.attributes.get("bound_verification_kinds")
    kinds = (
        tuple(sorted({str(item) for item in raw_kinds}))
        if isinstance(raw_kinds, list)
        else ()
    )
    raw_task_id = screen.provenance.get("authored_by_task_id")
    try:
        task_id = UUID(str(raw_task_id)) if raw_task_id else None
    except ValueError:
        task_id = None
    raw_oracle = screen.attributes.get("acceptance_oracle_version")
    oracle_version = (
        str(raw_oracle) if isinstance(raw_oracle, str) and raw_oracle else None
    )
    missing: list[str] = []
    if not kinds:
        missing.append("bound_verification_kinds")
    if task_id is None:
        missing.append("authored_by_task_id")
    if oracle_version is None:
        missing.append("acceptance_oracle_version")
    if missing:
        return VerificationBinding(
            task_id,
            oracle_version,
            kinds,
            "BLOCKED",
            "screen acceptance binding is incomplete: " + ", ".join(missing),
        )
    return VerificationBinding(task_id, oracle_version, kinds, "PENDING", None)


class CandidateVerificationRequestService:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        mutations: MutationExecutor | None = None,
    ) -> None:
        self._engine = engine
        self._mutations = mutations or MutationExecutor(engine)
        self._oracles = AcceptanceOracleRepository()

    async def schedule_live_preview(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        preview: FrontendPreviewSession,
    ) -> FrontendVerificationRequest:
        if PreviewState(preview.state) is not PreviewState.LIVE:
            raise ValueError(
                "verification requests may only be scheduled for LIVE previews"
            )
        existing = await self.for_preview(
            tenant_id=tenant_id,
            project_id=project_id,
            preview_session_id=preview.preview_session_id,
        )
        if existing is not None:
            return existing
        graph = await self._mutations.candidate_graph(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=preview.candidate_id,
        )
        binding = derive_verification_binding(graph, preview.screen_key)
        state = binding.state
        reason = binding.reason
        if state == "PENDING" and binding.task_id and binding.acceptance_oracle_version:
            async with open_unit_of_work(
                self._engine, tenant_id=tenant_id, project_id=project_id
            ) as uow:
                oracle = await self._oracles.get_by_version(
                    uow.connection, binding.task_id, binding.acceptance_oracle_version
                )
            if oracle is None:
                state = "BLOCKED"
                reason = "the screen's bound AcceptanceOracle cannot be resolved"
        now = datetime.now(UTC)
        record = FrontendVerificationRequest(
            verification_request_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=preview.mission_id,
            candidate_id=preview.candidate_id,
            preview_session_id=preview.preview_session_id,
            screen_key=preview.screen_key,
            viewport=preview.viewport,
            candidate_pxg_revision=preview.candidate_pxg_revision,
            source_revision=preview.source_revision,
            content_hash=preview.content_hash,
            task_id=binding.task_id,
            acceptance_oracle_version=binding.acceptance_oracle_version,
            required_kinds=list(binding.required_kinds),
            state=state,
            reason=reason,
            verification_run_ids=[],
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                pg_insert(frontend_verification_requests)
                .values(**record.model_dump())
                .on_conflict_do_nothing(index_elements=["preview_session_id"])
            )
            await uow.commit()
        resolved = await self.for_preview(
            tenant_id=tenant_id,
            project_id=project_id,
            preview_session_id=preview.preview_session_id,
        )
        if resolved is None:  # pragma: no cover - defensive database invariant
            raise RuntimeError(
                "verification request insert completed without a readable row"
            )
        return resolved

    async def for_preview(
        self, *, tenant_id: UUID, project_id: UUID, preview_session_id: UUID
    ) -> FrontendVerificationRequest | None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_verification_requests).where(
                            frontend_verification_requests.c.tenant_id == tenant_id,
                            frontend_verification_requests.c.project_id == project_id,
                            frontend_verification_requests.c.preview_session_id
                            == preview_session_id,
                        )
                    )
                )
                .mappings()
                .first()
            )
        return FrontendVerificationRequest.model_validate(dict(row)) if row else None

    async def latest_for_candidate(
        self, *, tenant_id: UUID, project_id: UUID, candidate_id: UUID
    ) -> FrontendVerificationRequest | None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_verification_requests)
                        .where(
                            frontend_verification_requests.c.tenant_id == tenant_id,
                            frontend_verification_requests.c.project_id == project_id,
                            frontend_verification_requests.c.candidate_id
                            == candidate_id,
                        )
                        .order_by(frontend_verification_requests.c.created_at.desc())
                        .limit(1)
                    )
                )
                .mappings()
                .first()
            )
        return FrontendVerificationRequest.model_validate(dict(row)) if row else None

    async def supersede_for_candidate(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        reason: str,
    ) -> tuple[UUID, ...]:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            rows = (
                (
                    await uow.connection.execute(
                        update(frontend_verification_requests)
                        .where(
                            frontend_verification_requests.c.tenant_id == tenant_id,
                            frontend_verification_requests.c.project_id == project_id,
                            frontend_verification_requests.c.candidate_id
                            == candidate_id,
                            frontend_verification_requests.c.state.in_(
                                ["PENDING", "BLOCKED"]
                            ),
                        )
                        .values(
                            state="SUPERSEDED",
                            reason=reason,
                            updated_at=now,
                            lock_version=frontend_verification_requests.c.lock_version
                            + 1,
                        )
                        .returning(
                            frontend_verification_requests.c.verification_request_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            await uow.commit()
        return tuple(rows)
