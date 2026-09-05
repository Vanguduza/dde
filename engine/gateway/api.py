"""HTTP surface for the gateway (Chapter 15.1, 15.4).

A thin transport boundary over `engine.gateway.sessions` and
`engine.gateway.commands`: session open/resume/close, the command-acceptance
path (202), and a mission read. The router itself holds no domain logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.client_session import ClientSession
from engine.contracts.command import Command
from engine.contracts.mission import Mission
from engine.contracts.mission_control import MissionControl
from engine.contracts.task import Task
from engine.contracts.task_graph import TaskGraph
from engine.core.errors import DdeError
from engine.gateway.commands import CommandAcceptance, GatewayCommandService
from engine.gateway.sessions.service import GatewaySessionService
from engine.gateway.settings import get_settings
from engine.truth.db import build_engine

router = APIRouter(prefix="/v1")

#: Chapter 15.5 error-family -> HTTP status (default retry metadata lives on
#: the `Error` contract's `retryable` field, not the status line alone).
_HTTP_STATUS = {
    # A client-supplied parameter that fails structural validation is a
    # 400: the request itself is malformed, which is distinct from a
    # well-formed request the policy layer refuses (403) and from a
    # well-formed request that conflicts with current state (409).
    "VALIDATION_FAILED": 400,
    "INVALID_CREDENTIALS": 401,
    "SESSION_EXPIRED": 401,
    "FORBIDDEN": 403,
    "POLICY_DENIED": 403,
    "TENANT_SCOPE_VIOLATION": 403,
    "NOT_FOUND": 404,
    # A required capability is not available to this build or principal.
    # A refusal, not an outage: the contract's `retryable` field carries
    # whether waiting would help, so the status line does not have to.
    "CAPABILITY_UNAVAILABLE": 403,
    # An external design/source artifact failed provenance, licence or
    # structural validation and may not be adopted.
    "DESIGN_SOURCE_REJECTED": 403,
    "VERSION_CONFLICT": 409,
    "RESOURCE_LOCKED": 409,
    "WRITE_SCOPE_CONFLICT": 409,
    "CONTEXT_INCOMPLETE": 409,
    "DIFF_STALE": 409,
    "CHECKPOINT_STALE": 409,
    "ACTIVITY_NOT_CANCELLABLE": 409,
    "PLAN_DEPENDENCY_BLOCKED": 409,
    "PLAN_NOT_APPROVED": 403,
    "COMMAND_NOT_ALLOWED": 403,
    "ATTACHMENT_TOO_LARGE": 413,
    "WORKSPACE_UNAVAILABLE": 503,
    # The caller's view of state is behind: same family as
    # VERSION_CONFLICT, and the fix is to re-read and replan.
    "STALE_REVISION": 409,
    "BUDGET_EXCEEDED": 409,
    "APPROVAL_REQUIRED": 403,
    "EVIDENCE_MISSING": 409,
    "EVIDENCE_CONFLICT": 409,
    "PROVIDER_UNAVAILABLE": 503,
    "PROVIDER_ERROR": 502,
    "PROVIDER_TIMEOUT": 504,
    "RESOURCE_EXHAUSTION": 413,
}


@dataclass(frozen=True)
class _Services:
    sessions: GatewaySessionService
    commands: GatewayCommandService


def _engine(request: Request) -> AsyncEngine:
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        engine = build_engine(get_settings().database_url)
        request.app.state.engine = engine
    return engine


def _services(request: Request) -> _Services:
    engine = _engine(request)
    return _Services(
        sessions=GatewaySessionService(engine),
        commands=GatewayCommandService(engine),
    )


async def dde_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map a domain error onto the Chapter 15.5 Error contract."""
    error = cast(DdeError, exc)
    status = _HTTP_STATUS.get(error.error_code, 500)
    return JSONResponse(
        status_code=status, content=error.to_contract().model_dump(mode="json")
    )


def _acceptance_dict(acceptance: CommandAcceptance) -> dict[str, object]:
    return {
        "command_id": str(acceptance.command_id),
        "status": acceptance.status,
        "target_type": acceptance.target_type,
        "target_id": str(acceptance.target_id),
        "payload": acceptance.payload,
    }


@router.post("/sessions", status_code=201, response_model=ClientSession)
async def open_session(request: Request) -> ClientSession:
    body = await request.json()
    return await _services(request).sessions.open_session(
        principal_id=UUID(body["principal_id"]),
        client_type=str(body["client_type"]),
        device_id=UUID(body["device_id"]) if body.get("device_id") else None,
        protocol_version=str(body.get("protocol_version", "1")),
        scopes=[str(item) for item in body["scopes"]],
        subscriptions=[str(item) for item in body.get("subscriptions", [])],
    )


@router.post("/sessions/{session_id}/resume")
async def resume_session(session_id: UUID, request: Request) -> dict[str, object]:
    body = await request.json()
    last_event_at_raw = body.get("last_event_at")
    last_event_at = (
        datetime.fromisoformat(last_event_at_raw) if last_event_at_raw else None
    )
    session, retained, fresh = await _services(request).sessions.resume(
        session_id=session_id, last_event_at=last_event_at
    )
    return {
        "session": session.model_dump(mode="json"),
        "fresh_snapshot": fresh,
        "events": [event.model_dump(mode="json") for event in retained],
    }


@router.post("/sessions/{session_id}/close", response_model=ClientSession)
async def close_session(session_id: UUID, request: Request) -> ClientSession:
    return await _services(request).sessions.close_session(session_id=session_id)


@router.post("/commands", status_code=202)
async def accept_command(command: Command, request: Request) -> dict[str, object]:
    return _acceptance_dict(await _services(request).commands.accept(command=command))


@router.get("/missions/{mission_id}/frontend/snapshot")
async def read_frontend_snapshot(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_snapshot(
        session_id=session_id, principal_id=principal_id, mission_id=mission_id
    )


@router.get("/missions/{mission_id}/frontend/audit/summary")
async def read_frontend_audit_summary(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_audit_summary(
        session_id=session_id, principal_id=principal_id, mission_id=mission_id
    )


@router.get("/missions/{mission_id}/frontend/audit/matrix")
async def read_frontend_audit_matrix(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_audit_matrix(
        session_id=session_id, principal_id=principal_id, mission_id=mission_id
    )


@router.get("/missions/{mission_id}/frontend/audit/screen")
async def read_frontend_audit_screen(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
    pxg_key: str,
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_audit_screen(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        pxg_key=pxg_key,
    )


@router.get("/missions/{mission_id}/frontend/audit/findings")
async def read_frontend_audit_findings(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
    pxg_key: str | None = None,
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_audit_findings(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        pxg_key=pxg_key,
    )


@router.get("/missions/{mission_id}/frontend/audit/findings/{finding_id}/evidence")
async def read_frontend_audit_evidence(
    mission_id: UUID,
    finding_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_audit_evidence(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        finding_id=finding_id,
    )


@router.get("/missions/{mission_id}/frontend/sources")
async def read_frontend_sources(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_sources(
        session_id=session_id, principal_id=principal_id, mission_id=mission_id
    )


@router.get("/missions/{mission_id}/frontend/sources/artifacts/{artifact_id}")
async def read_frontend_source_artifact(
    mission_id: UUID,
    artifact_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_source_artifact(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        artifact_id=artifact_id,
    )


@router.get("/missions/{mission_id}/frontend/sources/provenance")
async def read_frontend_source_provenance(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
    subject_kind: str,
    subject_ref: str,
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_source_provenance(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        subject_kind=subject_kind,
        subject_ref=subject_ref,
    )


@router.get("/missions/{mission_id}/frontend/sources/target-blend")
async def read_frontend_source_target_blend(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
    scope_key: str = "*",
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_source_target_blend(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        scope_key=scope_key,
    )


@router.get("/missions/{mission_id}/frontend/sources/candidates/{candidate_id}/score")
async def read_frontend_candidate_score(
    mission_id: UUID,
    candidate_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_candidate_score(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        candidate_id=candidate_id,
    )


@router.get("/missions/{mission_id}/chat/latest")
@router.get("/missions/{mission_id}/frontend/chat")
async def read_frontend_chat(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_chat(
        session_id=session_id, principal_id=principal_id, mission_id=mission_id
    )


@router.get("/missions/{mission_id}/chat/conversations")
@router.get("/missions/{mission_id}/frontend/chats")
async def read_frontend_chats(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
    query: str | None = None,
    include_archived: bool = False,
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_chats(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        query=query,
        include_archived=include_archived,
    )


@router.get("/missions/{mission_id}/chat/models")
@router.get("/missions/{mission_id}/frontend/chats/models")
async def read_frontend_chat_models(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_chat_models(
        session_id=session_id, principal_id=principal_id, mission_id=mission_id
    )


@router.get("/missions/{mission_id}/chat/conversations/{conversation_id}")
@router.get("/missions/{mission_id}/frontend/chats/{conversation_id}")
async def read_frontend_chat_by_id(
    mission_id: UUID,
    conversation_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_chat_by_id(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        conversation_id=conversation_id,
    )


@router.get("/missions/{mission_id}/chat/conversations/{conversation_id}/attachments")
@router.get("/missions/{mission_id}/frontend/chats/{conversation_id}/attachments")
async def read_frontend_chat_attachments(
    mission_id: UUID,
    conversation_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_chat_attachments(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        conversation_id=conversation_id,
    )


@router.put(
    "/missions/{mission_id}/chat/conversations/{conversation_id}/attachments/{attachment_id}/content"
)
@router.put(
    "/missions/{mission_id}/frontend/chats/{conversation_id}/attachments/{attachment_id}/content"
)
async def upload_frontend_chat_attachment(
    mission_id: UUID,
    conversation_id: UUID,
    attachment_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
    idempotency_key: Annotated[str, Header(alias="X-Idempotency-Key")],
) -> dict[str, object]:
    return await _services(request).commands.complete_frontend_chat_attachment_upload(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        conversation_id=conversation_id,
        attachment_id=attachment_id,
        content=await request.body(),
        idempotency_key=idempotency_key,
    )


@router.get("/missions/{mission_id}/chat/conversations/{conversation_id}/plans")
@router.get("/missions/{mission_id}/frontend/chats/{conversation_id}/plans")
async def read_frontend_chat_plans(
    mission_id: UUID,
    conversation_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_chat_plans(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        conversation_id=conversation_id,
    )


@router.get("/missions/{mission_id}/chat/conversations/{conversation_id}/activities")
@router.get("/missions/{mission_id}/frontend/chats/{conversation_id}/activities")
async def read_frontend_chat_activities(
    mission_id: UUID,
    conversation_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_chat_activities(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        conversation_id=conversation_id,
    )


@router.get("/missions/{mission_id}/chat/conversations/{conversation_id}/checkpoints")
@router.get("/missions/{mission_id}/frontend/chats/{conversation_id}/checkpoints")
async def read_frontend_chat_checkpoints(
    mission_id: UUID,
    conversation_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_chat_checkpoints(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        conversation_id=conversation_id,
    )


@router.get("/missions/{mission_id}/chat/conversations/{conversation_id}/changes")
@router.get("/missions/{mission_id}/frontend/chats/{conversation_id}/changes")
async def read_frontend_chat_changes(
    mission_id: UUID,
    conversation_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_chat_changes(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        conversation_id=conversation_id,
    )


@router.get("/missions/{mission_id}/chat/conversations/{conversation_id}/context")
@router.get("/missions/{mission_id}/frontend/chats/{conversation_id}/context")
async def read_frontend_chat_context(
    mission_id: UUID,
    conversation_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
    refs: str = "",
    budget_tokens: int = 24_000,
) -> dict[str, object]:
    parsed_refs = tuple(item.strip() for item in refs.split(",") if item.strip())
    return await _services(request).commands.read_frontend_chat_context_budget(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        conversation_id=conversation_id,
        refs=parsed_refs,
        budget_tokens=budget_tokens,
    )


@router.get("/missions/{mission_id}/chat/conversations/{conversation_id}/memory/recall")
async def read_dde_chat_memory_recall(
    mission_id: UUID,
    conversation_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
    query: str,
    budget_tokens: int = 4_000,
) -> dict[str, object]:
    return await _services(request).commands.read_dde_chat_memory_recall(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        conversation_id=conversation_id,
        query=query,
        budget_tokens=budget_tokens,
    )


@router.get("/missions/{mission_id}/frontend/fabric")
async def read_frontend_fabric(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
    conversation_id: UUID | None = None,
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_fabric_snapshot(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        conversation_id=conversation_id,
    )


@router.get("/missions/{mission_id}/frontend/fabric/memory")
async def read_frontend_fabric_memory(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
    scope_kind: str,
    scope_ref: str,
    status: str | None = None,
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_fabric_memory(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        scope_kind=scope_kind,
        scope_ref=scope_ref,
        status=status,
    )


@router.get("/missions/{mission_id}/frontend/fabric/claims/{turn_id}")
async def read_frontend_fabric_claims(
    mission_id: UUID,
    turn_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_fabric_claims(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        turn_id=turn_id,
    )


@router.get("/missions/{mission_id}/frontend/fabric/experience")
async def read_frontend_fabric_experience(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
    task_id: UUID | None = None,
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_fabric_experience(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        task_id=task_id,
    )


@router.get("/missions/{mission_id}/frontend/fabric/insights")
async def read_frontend_fabric_insights(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
    state: str | None = None,
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_fabric_insights(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        state=state,
    )


@router.get("/missions/{mission_id}/frontend/previews/{preview_session_id}")
async def read_frontend_preview(
    mission_id: UUID,
    preview_session_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_preview(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        preview_session_id=preview_session_id,
    )


@router.get("/missions/{mission_id}/frontend/inspector/{candidate_id}")
async def read_frontend_inspector(
    mission_id: UUID,
    candidate_id: UUID,
    pxg_key: str,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> dict[str, object]:
    return await _services(request).commands.read_frontend_inspector(
        session_id=session_id,
        principal_id=principal_id,
        mission_id=mission_id,
        candidate_id=candidate_id,
        pxg_key=pxg_key,
    )


@router.get("/missions/{mission_id}", response_model=Mission)
async def read_mission(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> Mission:
    return await _services(request).commands.read_mission(
        session_id=session_id, principal_id=principal_id, mission_id=mission_id
    )


@router.get("/tasks/{task_id}", response_model=Task)
async def read_task(
    task_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> Task:
    return await _services(request).commands.read_task(
        session_id=session_id, principal_id=principal_id, task_id=task_id
    )


@router.get("/task-graphs/{graph_id}", response_model=TaskGraph)
async def read_task_graph(
    graph_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> TaskGraph:
    return await _services(request).commands.read_task_graph(
        session_id=session_id, principal_id=principal_id, graph_id=graph_id
    )


@router.get("/mission-control/{mission_id}", response_model=MissionControl)
async def read_mission_control(
    mission_id: UUID,
    request: Request,
    session_id: Annotated[UUID, Header(alias="X-Session-Id")],
    principal_id: Annotated[UUID, Header(alias="X-Principal-Id")],
) -> MissionControl:
    return await _services(request).commands.read_mission_control(
        session_id=session_id, principal_id=principal_id, mission_id=mission_id
    )
