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
    "INVALID_CREDENTIALS": 401,
    "SESSION_EXPIRED": 401,
    "FORBIDDEN": 403,
    "POLICY_DENIED": 403,
    "TENANT_SCOPE_VIOLATION": 403,
    "VERSION_CONFLICT": 409,
    "RESOURCE_LOCKED": 409,
    "WRITE_SCOPE_CONFLICT": 409,
    "CONTEXT_INCOMPLETE": 409,
    "BUDGET_EXCEEDED": 409,
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
