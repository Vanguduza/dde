"""DDE-069 code-backed PreviewService.

PreviewService owns preview-session truth and the candidate materialization
lifecycle. It cannot promote accepted design and it cannot infer LIVE from a
successful command: LIVE is only written after a browser handshake is checked
against the candidate workspace, source hash and current PXG revisions.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_preview_session import FrontendPreviewSession
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.candidates.lifecycle import CandidateState
from engine.studio.candidates.service import CandidateService
from engine.studio.mutations.executor import MutationExecutor
from engine.studio.preview_runtime.prototype_html import PrototypeHtmlPreviewAdapter
from engine.studio.preview_runtime.runtime import PreviewRuntimeAdapter
from engine.studio.tables import frontend_preview_sessions
from engine.truth.db import open_unit_of_work
from engine.workspaces.service import WorkspaceService


class PreviewState(StrEnum):
    BUILDING = "BUILDING"
    LOADING = "LOADING"
    LIVE = "LIVE"
    STALE = "STALE"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    RENDER_ERROR = "RENDER_ERROR"
    UNAVAILABLE = "UNAVAILABLE"
    STOPPED = "STOPPED"


_ALLOWED: dict[PreviewState, frozenset[PreviewState]] = {
    PreviewState.BUILDING: frozenset(
        {
            PreviewState.LOADING,
            PreviewState.STALE,
            PreviewState.RENDER_ERROR,
            PreviewState.UNAVAILABLE,
            PreviewState.STOPPED,
        }
    ),
    PreviewState.LOADING: frozenset(
        {
            PreviewState.LIVE,
            PreviewState.STALE,
            PreviewState.RUNTIME_ERROR,
            PreviewState.RENDER_ERROR,
            PreviewState.STOPPED,
        }
    ),
    PreviewState.LIVE: frozenset(
        {
            PreviewState.STALE,
            PreviewState.RUNTIME_ERROR,
            PreviewState.RENDER_ERROR,
            PreviewState.STOPPED,
        }
    ),
    PreviewState.STALE: frozenset({PreviewState.STOPPED}),
    PreviewState.RUNTIME_ERROR: frozenset({PreviewState.STOPPED}),
    PreviewState.RENDER_ERROR: frozenset({PreviewState.STOPPED}),
    PreviewState.UNAVAILABLE: frozenset({PreviewState.STOPPED}),
    PreviewState.STOPPED: frozenset(),
}


@dataclass(frozen=True)
class PreviewDocumentRead:
    session: FrontendPreviewSession
    content: str


class PreviewService:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        workspaces: WorkspaceService | None = None,
        candidates: CandidateService | None = None,
        mutations: MutationExecutor | None = None,
        adapter: PreviewRuntimeAdapter | None = None,
    ) -> None:
        self._engine = engine
        self._workspaces = workspaces or WorkspaceService(engine)
        self._candidates = candidates or CandidateService(engine)
        self._mutations = mutations or MutationExecutor(
            engine, candidates=self._candidates
        )
        self._adapter = adapter or PrototypeHtmlPreviewAdapter(self._workspaces)

    async def start(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        screen_key: str,
        viewport: str,
        source_workspace_id: UUID | None = None,
    ) -> FrontendPreviewSession:
        view = await self._candidates.view(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
        )
        candidate = view.candidate
        if view.stale:
            return await self._create_session(
                candidate=candidate,
                screen_key=screen_key,
                viewport=viewport,
                state=PreviewState.STALE,
                candidate_pxg_revision=candidate.base_pxg_revision,
                state_detail=(
                    "accepted PXG advanced beyond this candidate base; rebase or "
                    "create a new candidate before previewing"
                ),
            )

        history = await self._mutations.history(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
        )
        graph = await self._mutations.candidate_graph(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
        )
        try:
            source_path = self._adapter.validate(
                graph=graph, history=history, screen_key=screen_key
            )
        except DdeError as exc:
            if exc.error_code != "CONTEXT_INCOMPLETE":
                raise
            return await self._create_session(
                candidate=candidate,
                screen_key=screen_key,
                viewport=viewport,
                state=PreviewState.UNAVAILABLE,
                candidate_pxg_revision=graph.revision,
                state_detail=exc.message,
            )

        workspace = None
        candidate_state = CandidateState(candidate.state)
        if candidate.workspace_id is not None:
            workspace = await self._workspaces.get_workspace(
                tenant_id=tenant_id,
                project_id=project_id,
                workspace_id=candidate.workspace_id,
            )
        elif candidate_state is CandidateState.GENERATED:
            if source_workspace_id is None:
                return await self._create_session(
                    candidate=candidate,
                    screen_key=screen_key,
                    viewport=viewport,
                    state=PreviewState.UNAVAILABLE,
                    candidate_pxg_revision=graph.revision,
                    source_path=source_path,
                    state_detail=(
                        "candidate has not materialized and no source workspace was "
                        "provided"
                    ),
                )
            source = await self._workspaces.get_workspace(
                tenant_id=tenant_id,
                project_id=project_id,
                workspace_id=source_workspace_id,
            )
            if source.status != "READY" or source.current_revision is None:
                return await self._create_session(
                    candidate=candidate,
                    screen_key=screen_key,
                    viewport=viewport,
                    state=PreviewState.UNAVAILABLE,
                    candidate_pxg_revision=graph.revision,
                    source_path=source_path,
                    state_detail="source workspace is not a durable READY revision",
                )
            workspace = await self._workspaces.create(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=candidate.mission_id,
                task_id=None,
                execution_environment_id=None,
                base_revision=source.current_revision,
                policy={
                    "purpose": "frontend_candidate_preview",
                    "candidate_id": str(candidate_id),
                },
            )
            try:
                candidate = await self._candidates.transition(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    candidate_id=candidate_id,
                    target=CandidateState.MATERIALIZING,
                    detail="isolated candidate worktree created",
                    workspace_id=workspace.workspace_id,
                )
            except Exception:
                await self._workspaces.cleanup(workspace=workspace)
                raise
            candidate_state = CandidateState(candidate.state)

        if workspace is None:
            return await self._create_session(
                candidate=candidate,
                screen_key=screen_key,
                viewport=viewport,
                state=PreviewState.UNAVAILABLE,
                candidate_pxg_revision=graph.revision,
                source_path=source_path,
                state_detail="candidate has no isolated workspace",
            )

        if candidate_state is CandidateState.MATERIALIZING:
            candidate = await self._candidates.transition(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
                target=CandidateState.RENDERING,
                detail="materializing code-backed preview",
            )
        elif candidate_state in {CandidateState.DIRTY, CandidateState.REPAIRING}:
            candidate = await self._candidates.transition(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
                target=CandidateState.RENDERING,
                detail="rerendering candidate after governed mutation",
            )
        elif candidate_state not in {CandidateState.RENDERING, CandidateState.READY}:
            return await self._create_session(
                candidate=candidate,
                screen_key=screen_key,
                viewport=viewport,
                state=PreviewState.UNAVAILABLE,
                candidate_pxg_revision=graph.revision,
                workspace_id=workspace.workspace_id,
                source_revision=workspace.current_revision,
                source_path=source_path,
                state_detail=(
                    f"candidate state {candidate.state} is not previewable; "
                    "it must be GENERATED, DIRTY, REPAIRING, RENDERING or READY"
                ),
            )

        session = await self._create_session(
            candidate=candidate,
            screen_key=screen_key,
            viewport=viewport,
            state=PreviewState.BUILDING,
            candidate_pxg_revision=graph.revision,
            workspace_id=workspace.workspace_id,
            source_revision=workspace.current_revision,
            source_path=source_path,
        )
        try:
            rendered = self._adapter.materialize(
                workspace=workspace,
                graph=graph,
                history=history,
                screen_key=screen_key,
                preview_session_id=session.preview_session_id,
            )
        except DdeError as exc:
            state = (
                PreviewState.UNAVAILABLE
                if exc.error_code == "CONTEXT_INCOMPLETE"
                else PreviewState.RENDER_ERROR
            )
            session = await self._transition_session(
                session,
                state,
                detail=exc.message,
            )
            if CandidateState(candidate.state) is CandidateState.RENDERING:
                await self._candidates.transition(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    candidate_id=candidate_id,
                    target=CandidateState.FAILED,
                    detail=f"preview {state.value.lower()}: {exc.message}",
                )
            return session

        if CandidateState(candidate.state) is CandidateState.RENDERING:
            await self._candidates.transition(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
                target=CandidateState.READY,
                detail="preview code materialized; awaiting browser load",
            )
        return await self._transition_session(
            session,
            PreviewState.LOADING,
            route=rendered.route,
            source_path=rendered.source_path,
            document_path=rendered.document_path,
            content_hash=rendered.content_hash,
            detail=(
                f"{len(rendered.instrumented_keys)} stable PXG anchor(s); "
                "awaiting browser ready handshake"
            ),
        )

    async def confirm_live(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        preview_session_id: UUID,
        content_hash: str,
    ) -> FrontendPreviewSession:
        session = await self.get(
            tenant_id=tenant_id,
            project_id=project_id,
            preview_session_id=preview_session_id,
        )
        if PreviewState(session.state) is not PreviewState.LOADING:
            return session
        candidate_view = await self._candidates.view(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=session.candidate_id,
        )
        candidate = candidate_view.candidate
        if candidate_view.stale:
            return await self._transition_session(
                session,
                PreviewState.STALE,
                detail="accepted PXG changed before the preview became live",
            )
        graph = await self._mutations.candidate_graph(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=session.candidate_id,
        )
        if (
            candidate.workspace_id != session.workspace_id
            or candidate.state != CandidateState.READY.value
            or graph.revision != session.candidate_pxg_revision
        ):
            return await self._transition_session(
                session,
                PreviewState.STALE,
                detail=(
                    "candidate workspace, state or effective graph changed after render"
                ),
            )
        if content_hash != session.content_hash:
            return await self._transition_session(
                session,
                PreviewState.STALE,
                detail="browser loaded a different candidate source hash",
            )
        if session.workspace_id is None or session.source_path is None:
            return await self._transition_session(
                session,
                PreviewState.STALE,
                detail="preview lost its candidate source mapping",
            )
        workspace = await self._workspaces.get_workspace(
            tenant_id=tenant_id,
            project_id=project_id,
            workspace_id=session.workspace_id,
        )
        actual_hash = hashlib.sha256(
            self._workspaces.read(workspace, session.source_path)
        ).hexdigest()
        if actual_hash != session.content_hash:
            return await self._transition_session(
                session,
                PreviewState.STALE,
                detail="candidate source changed after the preview document was built",
            )
        return await self._transition_session(
            session,
            PreviewState.LIVE,
            detail="browser loaded the exact code-backed candidate source",
        )

    async def report_runtime_error(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        preview_session_id: UUID,
        detail: str,
    ) -> FrontendPreviewSession:
        session = await self.get(
            tenant_id=tenant_id,
            project_id=project_id,
            preview_session_id=preview_session_id,
        )
        if PreviewState(session.state) not in {PreviewState.LOADING, PreviewState.LIVE}:
            return session
        return await self._transition_session(
            session, PreviewState.RUNTIME_ERROR, detail=detail
        )

    async def stop(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        preview_session_id: UUID,
    ) -> FrontendPreviewSession:
        session = await self.get(
            tenant_id=tenant_id,
            project_id=project_id,
            preview_session_id=preview_session_id,
        )
        if PreviewState(session.state) is PreviewState.STOPPED:
            return session
        return await self._transition_session(
            session, PreviewState.STOPPED, detail="preview session stopped"
        )

    async def document(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        preview_session_id: UUID,
    ) -> PreviewDocumentRead:
        session = await self.get(
            tenant_id=tenant_id,
            project_id=project_id,
            preview_session_id=preview_session_id,
        )
        if session.workspace_id is None or session.document_path is None:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "preview session has no materialized document",
                retryable=False,
                details={"preview_session_id": str(preview_session_id)},
            )
        workspace = await self._workspaces.get_workspace(
            tenant_id=tenant_id,
            project_id=project_id,
            workspace_id=session.workspace_id,
        )
        try:
            content = self._workspaces.read(workspace, session.document_path).decode(
                "utf-8"
            )
        except FileNotFoundError as exc:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "materialized preview document is absent from the candidate workspace",
                retryable=False,
                details={"document_path": session.document_path},
            ) from exc
        return PreviewDocumentRead(session=session, content=content)

    async def latest_for_candidate(
        self, *, tenant_id: UUID, project_id: UUID, candidate_id: UUID
    ) -> FrontendPreviewSession | None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_preview_sessions)
                .where(
                    frontend_preview_sessions.c.tenant_id == tenant_id,
                    frontend_preview_sessions.c.project_id == project_id,
                    frontend_preview_sessions.c.candidate_id == candidate_id,
                )
                .order_by(frontend_preview_sessions.c.created_at.desc())
                .limit(1)
            )
            row = result.mappings().first()
        return FrontendPreviewSession.model_validate(dict(row)) if row else None

    async def get(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        preview_session_id: UUID,
    ) -> FrontendPreviewSession:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_preview_sessions).where(
                    frontend_preview_sessions.c.preview_session_id
                    == preview_session_id,
                    frontend_preview_sessions.c.tenant_id == tenant_id,
                    frontend_preview_sessions.c.project_id == project_id,
                )
            )
            row = result.mappings().first()
        if row is None:
            raise DdeError(
                "POLICY_DENIED",
                "unknown preview session in this project",
                retryable=False,
                details={"preview_session_id": str(preview_session_id)},
            )
        return FrontendPreviewSession.model_validate(dict(row))

    async def _create_session(
        self,
        *,
        candidate: object,
        screen_key: str,
        viewport: str,
        state: PreviewState,
        candidate_pxg_revision: int,
        workspace_id: UUID | None = None,
        source_revision: str | None = None,
        source_path: str | None = None,
        state_detail: str | None = None,
    ) -> FrontendPreviewSession:
        from engine.contracts.frontend_candidate import FrontendCandidate

        if not isinstance(candidate, FrontendCandidate):
            raise TypeError("candidate must be FrontendCandidate")
        now = datetime.now(UTC)
        record = FrontendPreviewSession(
            preview_session_id=uuid7(),
            tenant_id=candidate.tenant_id,
            project_id=candidate.project_id,
            mission_id=candidate.mission_id,
            candidate_id=candidate.candidate_id,
            workspace_id=workspace_id,
            screen_key=screen_key,
            state=state.value,
            viewport=viewport,
            route=None,
            candidate_pxg_revision=candidate_pxg_revision,
            source_revision=source_revision,
            document_path=None,
            content_hash=None,
            state_detail=state_detail,
            lock_version=1,
            created_at=now,
            updated_at=now,
            source_path=source_path,
        )
        async with open_unit_of_work(
            self._engine,
            tenant_id=candidate.tenant_id,
            project_id=candidate.project_id,
        ) as uow:
            await uow.connection.execute(
                frontend_preview_sessions.insert().values(**record.model_dump())
            )
            await uow.commit()
        return record

    async def _transition_session(
        self,
        session: FrontendPreviewSession,
        target: PreviewState,
        *,
        detail: str | None = None,
        route: str | None = None,
        source_path: str | None = None,
        document_path: str | None = None,
        content_hash: str | None = None,
    ) -> FrontendPreviewSession:
        current = PreviewState(session.state)
        if target not in _ALLOWED[current]:
            raise DdeError(
                "POLICY_DENIED",
                "illegal preview state transition",
                retryable=False,
                details={
                    "from": current.value,
                    "to": target.value,
                    "allowed": sorted(item.value for item in _ALLOWED[current]),
                },
            )
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "state": target.value,
            "state_detail": detail,
            "updated_at": now,
            "lock_version": frontend_preview_sessions.c.lock_version + 1,
        }
        if route is not None:
            values["route"] = route
        if source_path is not None:
            values["source_path"] = source_path
        if document_path is not None:
            values["document_path"] = document_path
        if content_hash is not None:
            values["content_hash"] = content_hash
        async with open_unit_of_work(
            self._engine,
            tenant_id=session.tenant_id,
            project_id=session.project_id,
        ) as uow:
            result = await uow.connection.execute(
                update(frontend_preview_sessions)
                .where(
                    frontend_preview_sessions.c.preview_session_id
                    == session.preview_session_id,
                    frontend_preview_sessions.c.lock_version == session.lock_version,
                )
                .values(**values)
                .returning(frontend_preview_sessions)
            )
            row = result.mappings().first()
            if row is None:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "preview session changed concurrently; re-read and retry",
                    retryable=True,
                    details={"preview_session_id": str(session.preview_session_id)},
                )
            await uow.commit()
        return FrontendPreviewSession.model_validate(dict(row))
