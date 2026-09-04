"""Durable, isolated preview runtime for a Frontend Studio candidate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_preview_session import FrontendPreviewSession
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.service import EventService
from engine.studio.candidates.lifecycle import CandidateState
from engine.studio.candidates.service import CandidateService
from engine.studio.inspector import InspectorSnapshot, project_inspector
from engine.studio.mutations.executor import MutationExecutor
from engine.studio.preview.render import DOCUMENT_PATH, render_candidate
from engine.studio.tables import frontend_preview_sessions
from engine.truth.db import open_unit_of_work
from engine.workspaces.service import WorkspaceService


@dataclass(frozen=True)
class PreviewSnapshot:
    session: FrontendPreviewSession
    document_html: str | None
    inspector: InspectorSnapshot | None

    def as_dict(self) -> dict[str, object]:
        return {
            "session": self.session.model_dump(mode="json"),
            "document_html": self.document_html,
            "inspector": self.inspector.as_dict() if self.inspector else None,
            "live": self.session.status == "READY" and self.document_html is not None,
        }


class PreviewService:
    """Sole writer of ``frontend_preview_sessions``."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        candidates: CandidateService | None = None,
        mutations: MutationExecutor | None = None,
        workspaces: WorkspaceService | None = None,
        events: EventService | None = None,
    ) -> None:
        self._engine = engine
        self._candidates = candidates or CandidateService(engine)
        self._mutations = mutations or MutationExecutor(
            engine, candidates=self._candidates
        )
        self._workspaces = workspaces or WorkspaceService(engine)
        self._events = events or EventService(engine)

    async def start(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        route_key: str,
    ) -> PreviewSnapshot:
        view = await self._candidates.view(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
        )
        candidate = view.candidate
        if view.stale:
            raise DdeError(
                "STALE_REVISION",
                "candidate base is behind the accepted PXG; rebase before preview",
                retryable=False,
                details={
                    "candidate_id": str(candidate_id),
                    "candidate_base_revision": candidate.base_pxg_revision,
                    "accepted_revision": view.current_pxg_revision,
                },
            )

        state = CandidateState(candidate.state)
        if state is CandidateState.READY:
            latest = await self.latest(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
            )
            if latest is not None and latest.session.status == "READY":
                return latest
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "candidate says READY but no current preview artifact exists",
                retryable=True,
                details={"candidate_id": str(candidate_id)},
            )
        if state not in {CandidateState.GENERATED, CandidateState.DIRTY}:
            raise DdeError(
                "POLICY_DENIED",
                "candidate is not ready to materialize or rerender",
                retryable=False,
                details={
                    "candidate_id": str(candidate_id),
                    "state": state.value,
                    "allowed": [
                        CandidateState.GENERATED.value,
                        CandidateState.DIRTY.value,
                    ],
                },
            )

        workspace = None
        try:
            if state is CandidateState.GENERATED:
                candidate = await self._candidates.transition(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    candidate_id=candidate_id,
                    target=CandidateState.MATERIALIZING,
                    detail="creating isolated preview workspace",
                )
                base_revision = candidate.provenance.get("base_code_revision")
                workspace = await self._workspaces.create(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=candidate.mission_id,
                    task_id=None,
                    execution_environment_id=None,
                    base_revision=(
                        str(base_revision) if isinstance(base_revision, str) else None
                    ),
                    policy={
                        "owner": "engine.studio.preview",
                        "candidate_id": str(candidate_id),
                        "write_scope": ["dde-preview/"],
                        "network": "DENY",
                    },
                )
                candidate = await self._candidates.transition(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    candidate_id=candidate_id,
                    target=CandidateState.RENDERING,
                    detail="materializing candidate preview",
                    workspace_id=workspace.workspace_id,
                )
            else:
                if candidate.workspace_id is None:
                    raise DdeError(
                        "CONTEXT_INCOMPLETE",
                        "dirty candidate has no isolated workspace",
                        retryable=False,
                        details={"candidate_id": str(candidate_id)},
                    )
                workspace = await self._workspaces.get_workspace(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    workspace_id=candidate.workspace_id,
                )
                candidate = await self._candidates.transition(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    candidate_id=candidate_id,
                    target=CandidateState.RENDERING,
                    detail="rerendering candidate after mutation",
                )

            graph = await self._mutations.candidate_graph(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
            )
            preview_session_id = uuid7()
            document = render_candidate(
                graph,
                candidate_id=candidate_id,
                preview_session_id=preview_session_id,
                route_key=route_key,
            )
            self._workspaces.write(workspace, DOCUMENT_PATH, document.content)
            now = datetime.now(UTC)
            session = FrontendPreviewSession(
                preview_session_id=preview_session_id,
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
                workspace_id=workspace.workspace_id,
                status="READY",
                candidate_pxg_revision=document.candidate_pxg_revision,
                route_key=document.route_key,
                document_path=DOCUMENT_PATH,
                document_sha256=document.content_sha256,
                selected_pxg_key=None,
                error_code=None,
                error_detail=None,
                built_at=now,
                lock_version=1,
                created_at=now,
                updated_at=now,
            )
            async with open_unit_of_work(
                self._engine, tenant_id=tenant_id, project_id=project_id
            ) as uow:
                await uow.connection.execute(
                    update(frontend_preview_sessions)
                    .where(
                        frontend_preview_sessions.c.candidate_id == candidate_id,
                        frontend_preview_sessions.c.status == "READY",
                    )
                    .values(status="STALE", updated_at=now)
                )
                await uow.connection.execute(
                    frontend_preview_sessions.insert().values(
                        **session.model_dump()
                    )
                )
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    mission_id=candidate.mission_id,
                    event_type="FrontendPreviewReady",
                    aggregate_type="frontend_preview_session",
                    aggregate_id=preview_session_id,
                    payload={
                        "candidate_id": str(candidate_id),
                        "workspace_id": str(workspace.workspace_id),
                        "candidate_pxg_revision": document.candidate_pxg_revision,
                        "route_key": route_key,
                        "document_sha256": document.content_sha256,
                    },
                    uow=uow,
                )
                await uow.commit()

            await self._candidates.transition(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
                target=CandidateState.READY,
                detail=f"preview ready at candidate PXG {graph.revision}",
            )
            return PreviewSnapshot(
                session=session,
                document_html=document.content.decode("utf-8"),
                inspector=None,
            )
        except DdeError as exc:
            await self._fail_candidate_if_possible(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
                detail=f"{exc.error_code}: {exc.message}",
            )
            raise

    async def latest(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
    ) -> PreviewSnapshot | None:
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
        if row is None:
            return None
        session = FrontendPreviewSession.model_validate(dict(row))
        if session.status != "READY":
            return PreviewSnapshot(session=session, document_html=None, inspector=None)

        graph = await self._mutations.candidate_graph(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
        )
        if graph.revision != session.candidate_pxg_revision:
            session = await self._mark_status(session, "STALE")
            return PreviewSnapshot(session=session, document_html=None, inspector=None)

        workspace = await self._workspaces.get_workspace(
            tenant_id=tenant_id,
            project_id=project_id,
            workspace_id=session.workspace_id,
        )
        content = self._workspaces.read(workspace, session.document_path)
        if sha256(content).hexdigest() != session.document_sha256:
            session = await self._mark_status(
                session,
                "RUNTIME_ERROR",
                error_code="INTEGRITY_FAILURE",
                error_detail="preview artifact hash no longer matches its durable record",
            )
            return PreviewSnapshot(session=session, document_html=None, inspector=None)

        inspector = None
        if session.selected_pxg_key:
            node = graph.node_by_key(session.selected_pxg_key)
            if node is not None:
                inspector = project_inspector(node)
        return PreviewSnapshot(
            session=session,
            document_html=content.decode("utf-8"),
            inspector=inspector,
        )

    async def select(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        preview_session_id: UUID,
        pxg_key: str,
        candidate_pxg_revision: int,
    ) -> PreviewSnapshot:
        session = await self._get(
            tenant_id=tenant_id,
            project_id=project_id,
            preview_session_id=preview_session_id,
        )
        if session.status != "READY":
            raise DdeError(
                "STALE_REVISION",
                "selection belongs to a preview that is no longer ready",
                retryable=True,
                details={"preview_status": session.status},
            )
        if candidate_pxg_revision != session.candidate_pxg_revision:
            raise DdeError(
                "STALE_REVISION",
                "selection event came from an older candidate render",
                retryable=True,
                details={
                    "event_revision": candidate_pxg_revision,
                    "preview_revision": session.candidate_pxg_revision,
                },
            )
        graph = await self._mutations.candidate_graph(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=session.candidate_id,
        )
        node = graph.node_by_key(pxg_key)
        if node is None or not _belongs_to_route(node.pxg_key, session.route_key, graph):
            raise DdeError(
                "POLICY_DENIED",
                "selection is not a node in this rendered route",
                retryable=False,
                details={"pxg_key": pxg_key, "route_key": session.route_key},
            )
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                update(frontend_preview_sessions)
                .where(
                    frontend_preview_sessions.c.preview_session_id
                    == preview_session_id,
                    frontend_preview_sessions.c.lock_version == session.lock_version,
                )
                .values(
                    selected_pxg_key=pxg_key,
                    lock_version=frontend_preview_sessions.c.lock_version + 1,
                    updated_at=now,
                )
                .returning(frontend_preview_sessions)
            )
            row = result.mappings().first()
            if row is None:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "preview selection changed concurrently",
                    retryable=True,
                )
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="FrontendPreviewSelectionChanged",
                aggregate_type="frontend_preview_session",
                aggregate_id=preview_session_id,
                payload={
                    "candidate_id": str(session.candidate_id),
                    "pxg_key": pxg_key,
                    "candidate_pxg_revision": candidate_pxg_revision,
                },
                uow=uow,
            )
            await uow.commit()
        updated = FrontendPreviewSession.model_validate(dict(row))
        current = await self.latest(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=updated.candidate_id,
        )
        if current is None:
            raise DdeError(
                "INTERNAL_ERROR",
                "selected preview disappeared",
                retryable=True,
            )
        return current

    async def _get(
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

    async def _mark_status(
        self,
        session: FrontendPreviewSession,
        status: str,
        *,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> FrontendPreviewSession:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine,
            tenant_id=session.tenant_id,
            project_id=session.project_id,
        ) as uow:
            result = await uow.connection.execute(
                update(frontend_preview_sessions)
                .where(
                    frontend_preview_sessions.c.preview_session_id
                    == session.preview_session_id
                )
                .values(
                    status=status,
                    error_code=error_code,
                    error_detail=error_detail,
                    updated_at=now,
                    lock_version=frontend_preview_sessions.c.lock_version + 1,
                )
                .returning(frontend_preview_sessions)
            )
            row = result.mappings().one()
            await uow.commit()
        return FrontendPreviewSession.model_validate(dict(row))

    async def _fail_candidate_if_possible(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        candidate_id: UUID,
        detail: str,
    ) -> None:
        candidate = await self._candidates.get(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=candidate_id,
        )
        state = CandidateState(candidate.state)
        if state in {CandidateState.MATERIALIZING, CandidateState.RENDERING}:
            await self._candidates.transition(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=candidate_id,
                target=CandidateState.FAILED,
                detail=detail,
            )


def _belongs_to_route(pxg_key: str, route_key: str, graph) -> bool:
    current = graph.node_by_key(pxg_key)
    seen: set[str] = set()
    while current is not None and current.pxg_key not in seen:
        if current.pxg_key == route_key:
            return True
        seen.add(current.pxg_key)
        current = (
            graph.node_by_key(current.parent_key) if current.parent_key else None
        )
    return False
