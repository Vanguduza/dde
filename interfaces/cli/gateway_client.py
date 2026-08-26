"""CLI Gateway /v1 client (DDE-056 client-parity surface).

Mirrors ``interfaces/dashboard/static/gateway.js`` and Android
``GatewayAllowlist`` — the same six endpoints, no invented lists or
streams. The Stage-1 ``dde mission create|status|trace`` commands still
call ``engine.*`` directly; this module is the Gateway path the golden
CLI/web/Android parity fixture exercises so all three clients share one
authoritative control plane (Ch.15.1/15.2).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final
from uuid import uuid4

import httpx

#: Must stay identical to dashboard ``GatewayApiClient.ALLOWED_PATHS`` and
#: Android ``GatewayAllowlist.ALLOWED_PATHS``.
ALLOWED_PATHS: Final[tuple[str, ...]] = (
    "POST /v1/sessions",
    "POST /v1/sessions/{id}/resume",
    "POST /v1/sessions/{id}/close",
    "POST /v1/commands",
    "GET /v1/missions/{id}",
    "GET /v1/mission-control/{id}",
)

#: Human operator scopes used by dashboard ``app.js`` and Android
#: ``HumanMissionScopes`` for Mission Control.
HUMAN_MISSION_SCOPES: Final[tuple[str, ...]] = (
    "mission.read",
    "mission.create",
    "mission.control",
    "approval.read",
    "approval.decide",
    "approval.request",
    "credential.capture",
)


class GatewayClient:
    """Thin async client over the allowlisted Gateway surface."""

    def __init__(self, http: httpx.AsyncClient, *, base_path: str = "/v1") -> None:
        self._http = http
        self._base = base_path.rstrip("/")

    async def open_session(
        self,
        *,
        principal_id: str,
        client_type: str = "human",
        scopes: list[str] | tuple[str, ...] | None = None,
        subscriptions: list[str] | None = None,
    ) -> dict[str, Any]:
        response = await self._http.post(
            f"{self._base}/sessions",
            json={
                "principal_id": principal_id,
                "client_type": client_type,
                "protocol_version": "1",
                "scopes": list(scopes if scopes is not None else HUMAN_MISSION_SCOPES),
                "subscriptions": subscriptions
                if subscriptions is not None
                else ["mission"],
            },
        )
        response.raise_for_status()
        return response.json()

    async def resume_session(
        self, session_id: str, *, last_event_at: str | None = None
    ) -> dict[str, Any]:
        response = await self._http.post(
            f"{self._base}/sessions/{session_id}/resume",
            json={"last_event_at": last_event_at},
        )
        response.raise_for_status()
        return response.json()

    async def close_session(self, session_id: str) -> dict[str, Any]:
        response = await self._http.post(
            f"{self._base}/sessions/{session_id}/close",
            json={},
        )
        response.raise_for_status()
        return response.json()

    async def accept_command(
        self,
        *,
        session_id: str,
        principal_id: str,
        command_type: str,
        target_type: str,
        target_id: str,
        parameters: dict[str, Any],
        idempotency_key: str,
        command_id: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """POST /v1/commands. Returns ``(http_status, body)``.

        Callers must treat 202 as acceptance only (Ch.15.2) and re-read
        authoritative state by id.
        """
        body = {
            "command_id": command_id or str(uuid4()),
            "idempotency_key": idempotency_key,
            "principal_id": principal_id,
            "client_session_id": session_id,
            "target_type": target_type,
            "target_id": target_id,
            "command_type": command_type,
            "parameters": parameters,
            "requested_at": datetime.now(UTC).isoformat(),
            "protocol_version": "1",
        }
        response = await self._http.post(f"{self._base}/commands", json=body)
        return response.status_code, response.json()

    async def read_mission(
        self, *, session_id: str, principal_id: str, mission_id: str
    ) -> dict[str, Any]:
        response = await self._http.get(
            f"{self._base}/missions/{mission_id}",
            headers={
                "X-Session-Id": session_id,
                "X-Principal-Id": principal_id,
            },
        )
        response.raise_for_status()
        return response.json()

    async def read_mission_control(
        self, *, session_id: str, principal_id: str, mission_id: str
    ) -> dict[str, Any]:
        response = await self._http.get(
            f"{self._base}/mission-control/{mission_id}",
            headers={
                "X-Session-Id": session_id,
                "X-Principal-Id": principal_id,
            },
        )
        response.raise_for_status()
        return response.json()
