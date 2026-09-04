"""Gateway command acceptance (Chapter 15.1, 15.2).

The gateway is a thin transport boundary: it authenticates and authorizes a
command before it reaches Core, enforces the idempotency key, and separates
command acceptance (202) from eventual completion. It never owns Project
Truth or mission state — the dispatched domain service is the authoritative
mutation (Chapter 15.1).

Approval commands (`approval.batch_decide`,
`approval.request_budget_increase`, `approval.decide_budget_increase`) are
dispatched onto `engine.governance.service.ApprovalService`, which keeps its
own Chapter 12.5 ledger entries for the batch and budget-request commands.
The gateway's outer ledger row stays authoritative for acceptance/replay;
the inner rows give each governance command a durable audit identity of its
own (Chapter 13.1 batch amendment, Ch.7.1/12.3 budget workflow).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.broker.capture import StaticSecretCaptureService
from engine.contracts.client_session import ClientSession
from engine.contracts.command import Command
from engine.contracts.mission import Mission
from engine.contracts.mission_control import MissionControl
from engine.contracts.task import Task
from engine.contracts.task_graph import TaskGraph
from engine.core.errors import DdeError
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.gateway.scopes import (
    MISSION_CONTROL_TARGETS,
    required_scope,
    required_target_type,
)
from engine.gateway.sessions.service import GatewaySessionService
from engine.governance.service import (
    ApprovalService,
    BatchDecisionResult,
    BudgetDecision,
    BudgetRequest,
)
from engine.missions.repository import MissionsRepository
from engine.missions.service import MissionService
from engine.planning.repository import TaskGraphRepository
from engine.projections.service import MissionControlService
from engine.studio.frontend import FrontendStudioService


@dataclass(frozen=True)
class CommandAcceptance:
    """202-accepted result (Chapter 15.1: acceptance is not completion)."""

    command_id: UUID
    status: str
    target_type: str
    target_id: UUID
    payload: dict[str, object]


def _hash_command(command: Command) -> str:
    """Fingerprint the logical command identity, excluding per-attempt fields
    (`command_id`, `idempotency_key`, `requested_at`, principal/session) so a
    true retry hashes identically while key reuse with a different logical
    command is refused (Chapter 12.5).

    For `credential.capture_opensandbox`, the raw `api_key` is replaced by its
    content hash before hashing so the outer ledger never fingerprints the
    live secret material itself — only the already-hashed digest.
    """
    parameters = command.parameters
    if command.command_type == "credential.capture_opensandbox":
        parameters = _redact_capture_parameters(dict(parameters))
    canonical = json.dumps(
        {
            "command_type": command.command_type,
            "target_type": command.target_type,
            "target_id": str(command.target_id),
            "parameters": parameters,
            "protocol_version": command.protocol_version,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _redact_capture_parameters(parameters: dict[str, object]) -> dict[str, object]:
    """Replace raw api_key with its SHA-256 digest for ledger fingerprinting."""
    from engine.core.hashing import sha256_hex

    redacted = dict(parameters)
    raw = redacted.get("api_key")
    if isinstance(raw, str) and raw.strip():
        redacted["api_key"] = sha256_hex(raw.strip())
    return redacted


def _param_str(parameters: dict[str, object], name: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str):
        raise DdeError(
            "FORBIDDEN",
            f"Missing or invalid parameter '{name}'",
            details={"parameter": name},
        )
    return value


def _param_list(parameters: dict[str, object], name: str) -> list[str]:
    value = parameters.get(name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise DdeError(
            "FORBIDDEN",
            f"Missing or invalid parameter '{name}'",
            details={"parameter": name},
        )
    return value


def _param_int(parameters: dict[str, object], name: str) -> int:
    value = parameters.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise DdeError(
            "FORBIDDEN",
            f"Missing or invalid parameter '{name}'",
            details={"parameter": name},
        )
    return value


def _param_int_opt(parameters: dict[str, object], name: str) -> int | None:
    """Optional integer parameter: absent means None, malformed means
    FORBIDDEN."""
    value = parameters.get(name)
    if value is None:
        return None
    return _param_int(parameters, name)


def _param_uuid(parameters: dict[str, object], name: str) -> UUID | None:
    """Parse one optional UUID-valued parameter. `None` means absent; a
    present-but-malformed value is a FORBIDDEN parameter error, not a
    silent default."""
    value = parameters.get(name)
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise DdeError(
            "FORBIDDEN",
            f"Missing or invalid parameter '{name}'",
            details={"parameter": name, "value": str(value)},
        ) from exc


def _param_uuid_list(parameters: dict[str, object], name: str) -> list[UUID]:
    value = parameters.get(name)
    if not isinstance(value, list):
        raise DdeError(
            "FORBIDDEN",
            f"Missing or invalid parameter '{name}'",
            details={"parameter": name},
        )
    parsed: list[UUID] = []
    for item in value:
        try:
            parsed.append(UUID(str(item)))
        except ValueError as exc:
            raise DdeError(
                "FORBIDDEN",
                f"Missing or invalid parameter '{name}'",
                details={"parameter": name, "value": item},
            ) from exc
    return parsed


class CommandDispatcher:
    """Dispatches an authorized command onto its owning domain service."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def _missions(self) -> MissionService:
        return MissionService(self._engine, EventService(self._engine))

    def _approvals(self) -> ApprovalService:
        return ApprovalService(self._engine)

    def _captures(self) -> StaticSecretCaptureService:
        return StaticSecretCaptureService(self._engine)

    async def load_mission(self, mission_id: UUID) -> Mission:
        async with self._engine.connect() as connection:
            mission = await MissionsRepository().get_mission(connection, mission_id)
        if mission is None:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown mission",
                details={"mission_id": str(mission_id)},
            )
        return mission

    async def load_task(self, task_id: UUID) -> Task:
        async with self._engine.connect() as connection:
            task = await MissionsRepository().get_task(connection, task_id)
        if task is None:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown task",
                details={"task_id": str(task_id)},
            )
        return task

    async def load_task_graph(self, graph_id: UUID) -> TaskGraph:
        async with self._engine.connect() as connection:
            graph = await TaskGraphRepository().get_task_graph(connection, graph_id)
        if graph is None:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown task graph",
                details={"graph_id": str(graph_id)},
            )
        return graph

    async def dispatch(
        self,
        *,
        command: Command,
        tenant_id: UUID,
        project_id: UUID,
    ) -> CommandAcceptance:
        command_type = command.command_type
        if command_type == "mission.create":
            return await self._create_mission(command, tenant_id, project_id)
        if command_type in MISSION_CONTROL_TARGETS:
            return await self._control_mission(
                command, tenant_id, project_id, command_type
            )
        if command_type == "approval.batch_decide":
            return await self._batch_decide(command, tenant_id, project_id)
        if command_type == "approval.request_budget_increase":
            return await self._request_budget_increase(command, tenant_id, project_id)
        if command_type == "approval.decide_budget_increase":
            return await self._decide_budget_increase(command, tenant_id, project_id)
        if command_type == "credential.capture_opensandbox":
            return await self._capture_opensandbox(command, tenant_id, project_id)
        if command_type == "credential.inspect_opensandbox":
            return await self._inspect_opensandbox(command, tenant_id, project_id)
        if command_type == "device.heartbeat":
            return await self._device_heartbeat(command, tenant_id, project_id)
        if command_type.startswith("frontend."):
            return await self._frontend(command, tenant_id, project_id, command_type)
        raise DdeError(
            "FORBIDDEN",
            "Unsupported command_type",
            details={"command_type": command_type},
        )

    async def _create_mission(
        self, command: Command, tenant_id: UUID, project_id: UUID
    ) -> CommandAcceptance:
        params = command.parameters
        mission = await self._missions().create_mission(
            tenant_id=tenant_id,
            project_id=project_id,
            slug=_param_str(params, "slug"),
            title=_param_str(params, "title"),
            intent=_param_str(params, "intent"),
            success_definition=_param_str(params, "success_definition"),
            scope=_param_list(params, "scope"),
            requirement_refs=_param_list(params, "requirement_refs"),
            autonomy_ceiling=_param_int(params, "autonomy_ceiling"),
        )
        return CommandAcceptance(
            command_id=command.command_id,
            status="accepted",
            target_type="mission",
            target_id=mission.mission_id,
            payload={"mission_id": str(mission.mission_id), "status": mission.status},
        )

    async def _control_mission(
        self,
        command: Command,
        tenant_id: UUID,
        project_id: UUID,
        command_type: str,
    ) -> CommandAcceptance:
        target_status = MISSION_CONTROL_TARGETS[command_type]
        params = command.parameters
        lock_version = _param_int(params, "lock_version")
        mission = await self._missions().transition_mission(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=command.target_id,
            target_status=target_status,
            lock_version=lock_version,
        )
        return CommandAcceptance(
            command_id=command.command_id,
            status="accepted",
            target_type="mission",
            target_id=mission.mission_id,
            payload={"mission_id": str(mission.mission_id), "status": mission.status},
        )

    async def _batch_decide(
        self, command: Command, tenant_id: UUID, project_id: UUID
    ) -> CommandAcceptance:
        """Chapter 13.1 batch-approve amendment over the command path.

        Parameters (all required unless noted): `approval_ids` (UUID
        strings), `scope_hashes` (parallel list), `decision`
        (`APPROVED`|`REJECTED`), `rationale`, optional `human_minutes`,
        optional `edr_id`. The command's own idempotency key is passed down
        so `ApprovalService.batch_decide` records the batch under it; a
        gateway-level replay therefore returns the stored first outcome
        without a second decision pass. `target_id` is the addressed
        project; the payload's primary identity is `batch_id` — the
        durable command identity of the batch itself.
        """
        params = command.parameters
        result = await self._approvals().batch_decide(
            tenant_id=tenant_id,
            project_id=project_id,
            approval_ids=_param_uuid_list(params, "approval_ids"),
            decision=_param_str(params, "decision"),
            decided_by=command.principal_id,
            rationale=_param_str(params, "rationale"),
            scope_hashes=_param_list(params, "scope_hashes"),
            human_minutes=float(_param_int_opt(params, "human_minutes") or 0),
            edr_id=_param_uuid(params, "edr_id"),
            # Namespaced inner key: the gateway's outer ledger owns the
            # raw command key; ApprovalService keeps its own Chapter 12.5
            # row under a derived one so the two `begin` calls never
            # collide on the same row with different request hashes.
            idempotency_key=f"approval.batch:{command.idempotency_key}",
        )
        return CommandAcceptance(
            command_id=command.command_id,
            status="accepted",
            target_type="approval_batch",
            target_id=result.batch_id or project_id,
            payload=batch_decision_payload(result),
        )

    async def _request_budget_increase(
        self, command: Command, tenant_id: UUID, project_id: UUID
    ) -> CommandAcceptance:
        """Human/service budget-request half (Ch.7.1/12.3) over the command
        path.

        Parameters: `mission_id`, `task_id` (required by the service: the
        request binds to exactly one task), `reason`, and at least one of
        `requested_max_tokens` / `requested_max_tool_calls`; optional
        `human_minutes` is not accepted here — a request costs no human
        minutes yet. The service records its own ledger row under a
        namespaced derivative of this command's idempotency key.
        `target_id` is the addressed project; the payload's primary
        identity is `approval_id` — the durable Approval a human later
        decides on.
        """
        params = command.parameters
        result = await self._approvals().request_budget_increase(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=_required_uuid_param(params, "mission_id"),
            task_id=_required_uuid_param(params, "task_id"),
            requested_by=command.principal_id,
            reason=_param_str(params, "reason"),
            requested_max_tokens=_param_int_opt(params, "requested_max_tokens"),
            requested_max_tool_calls=_param_int_opt(params, "requested_max_tool_calls"),
            # Namespaced inner key -- see `_batch_decide`.
            idempotency_key=f"approval.budget_request:{command.idempotency_key}",
        )
        return CommandAcceptance(
            command_id=command.command_id,
            status="accepted",
            target_type="budget_request",
            target_id=result.approval.approval_id,
            payload=budget_request_payload(result),
        )

    async def _decide_budget_increase(
        self, command: Command, tenant_id: UUID, project_id: UUID
    ) -> CommandAcceptance:
        """Human budget-decision half (Ch.7.1/12.3) over the command path.

        Parameters: `approval_id` (the `budget_increase` approval),
        `decision` (`APPROVED`|`REJECTED`), `rationale`, optional
        `human_minutes`. On APPROVED the service re-plans the bound task
        with the raised ceiling in the same transaction; on REJECTED
        nothing is widened. `target_id` is the addressed project; the
        payload's primary identity is `approval_id`.
        """
        params = command.parameters
        result = await self._approvals().decide_budget_increase(
            tenant_id=tenant_id,
            project_id=project_id,
            approval_id=_required_uuid_param(params, "approval_id"),
            decided_by=command.principal_id,
            decision=_param_str(params, "decision"),
            rationale=_param_str(params, "rationale"),
            human_minutes=float(_param_int_opt(params, "human_minutes") or 0),
        )
        return CommandAcceptance(
            command_id=command.command_id,
            status="accepted",
            target_type="budget_request",
            target_id=result.approval.approval_id,
            payload=budget_decision_payload(result),
        )

    async def _capture_opensandbox(
        self, command: Command, tenant_id: UUID, project_id: UUID
    ) -> CommandAcceptance:
        """Studio Settings paste → hash → broker capture for OpenSandbox.

        Parameters: `api_key` (required), optional `domain`. The raw key is
        never returned in the acceptance payload — only fingerprint / last4 /
        captured metadata. Inner ledger key is namespaced so it does not
        collide with the gateway outer CommandLedger row.
        """
        params = command.parameters
        domain_raw = params.get("domain")
        domain = (
            domain_raw.strip()
            if isinstance(domain_raw, str) and domain_raw.strip()
            else None
        )
        result = await self._captures().capture_opensandbox_api_key(
            tenant_id=tenant_id,
            project_id=project_id,
            api_key=_param_str(params, "api_key"),
            domain=domain,
            captured_by=str(command.principal_id),
            idempotency_key=f"credential.capture:{command.idempotency_key}",
        )
        payload = StaticSecretCaptureService.public_status(result.record)
        payload["replayed"] = result.replayed
        return CommandAcceptance(
            command_id=command.command_id,
            status="accepted",
            target_type="project",
            target_id=project_id,
            payload=payload,
        )

    async def _inspect_opensandbox(
        self, command: Command, tenant_id: UUID, project_id: UUID
    ) -> CommandAcceptance:
        """Return captured OpenSandbox fingerprint chip (never the raw key)."""
        active = await self._captures().inspect(
            tenant_id=tenant_id, project_id=project_id
        )
        if active is None:
            payload: dict[str, object] = {
                "captured": False,
                "provider_id": "opensandbox_api_key",
            }
        else:
            payload = StaticSecretCaptureService.public_status(active)
        return CommandAcceptance(
            command_id=command.command_id,
            status="accepted",
            target_type="project",
            target_id=project_id,
            payload=payload,
        )

    async def _device_heartbeat(
        self, command: Command, tenant_id: UUID, project_id: UUID
    ) -> CommandAcceptance:
        """Minimal device liveness command (DDE-054 / Ch.14.2).

        Acceptance only — no Project Truth or mission mutation. The outer
        CommandLedger still records the idempotency key so offline flush
        cannot mint a second mutation (Ch.15.2 / Ch.12.5).
        """
        return CommandAcceptance(
            command_id=command.command_id,
            status="accepted",
            target_type="device",
            target_id=command.target_id,
            payload={
                "ok": True,
                "device_id": str(command.target_id),
                "project_id": str(project_id),
                "tenant_id": str(tenant_id),
            },
        )

    def _studio(self) -> FrontendStudioService:
        return FrontendStudioService(self._engine)

    async def _frontend(
        self,
        command: Command,
        tenant_id: UUID,
        project_id: UUID,
        command_type: str,
    ) -> CommandAcceptance:
        """DDE-067 Frontend Studio commands. Domain mutation is
        FrontendStudioService; this method only maps parameters."""
        studio = self._studio()
        params = command.parameters
        mission_id = command.target_id
        key = command.idempotency_key
        if command_type == "frontend.intake.compile_prompt":
            payload = await studio.compile_prompt(parameters=params)
        elif command_type == "frontend.donors.run_discovery":
            payload = await studio.run_discovery(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                idempotency_key=key,
                parameters=params,
            )
        elif command_type == "frontend.donors.submit_uri":
            payload = await studio.submit_uri(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                idempotency_key=key,
                parameters=params,
            )
        elif command_type == "frontend.donors.request_adoption":
            payload = await studio.request_adoption(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                principal_id=command.principal_id,
                idempotency_key=key,
                parameters=params,
            )
        elif command_type == "frontend.prototype.request_pixel_signoff":
            payload = await studio.request_pixel_signoff(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                principal_id=command.principal_id,
                idempotency_key=key,
                parameters=params,
            )
        elif command_type == "frontend.contract.publish":
            payload = await studio.publish_contract(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                parameters=params,
            )
        elif command_type == "frontend.pxg.apply":
            payload = await studio.apply_pxg(
                tenant_id=tenant_id,
                project_id=project_id,
                parameters=params,
            )
        elif command_type == "frontend.coverage.recompute":
            payload = await studio.recompute_coverage(
                tenant_id=tenant_id,
                project_id=project_id,
                parameters=params,
            )
        elif command_type == "frontend.canvas.insert_component":
            payload = await studio.insert_component(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                parameters=params,
            )
        elif command_type == "frontend.canvas.update_element":
            payload = await studio.update_element(
                tenant_id=tenant_id,
                project_id=project_id,
                parameters=params,
            )
        elif command_type == "frontend.canvas.move_component":
            payload = await studio.move_component(
                tenant_id=tenant_id,
                project_id=project_id,
                parameters=params,
            )
        elif command_type == "frontend.canvas.remove_element":
            payload = await studio.remove_element(
                tenant_id=tenant_id,
                project_id=project_id,
                parameters=params,
            )
        elif command_type == "frontend.motion.set_animation":
            payload = await studio.set_animation(
                tenant_id=tenant_id,
                project_id=project_id,
                parameters=params,
            )
        elif command_type == "frontend.flow.upsert_step":
            payload = await studio.upsert_step(
                tenant_id=tenant_id,
                project_id=project_id,
                parameters=params,
            )
        else:
            raise DdeError(
                "FORBIDDEN",
                "Unsupported command_type",
                details={"command_type": command_type},
            )
        return CommandAcceptance(
            command_id=command.command_id,
            status="accepted",
            target_type="mission",
            target_id=mission_id,
            payload=payload,
        )


def _required_uuid_param(parameters: dict[str, object], name: str) -> UUID:
    value = _param_uuid(parameters, name)
    if value is None:
        raise DdeError(
            "FORBIDDEN",
            f"Missing or invalid parameter '{name}'",
            details={"parameter": name},
        )
    return value


def _uuid_or_none(value: UUID | None) -> str | None:
    return None if value is None else str(value)


def _int_or_none(value: int | None) -> int | None:
    return value


def batch_decision_payload(result: BatchDecisionResult) -> dict[str, object]:
    """JSON-able Chapter 13.1 batch outcome. `batch_id` is the batch's own
    durable command identity (None when the caller supplied none); every
    member carries its post-decision state with all UUIDs stringified."""
    return {
        "batch_id": _uuid_or_none(result.batch_id),
        "decision": result.decision,
        "decided_by": str(result.decided_by),
        "created_at": result.created_at.isoformat(),
        "replayed": result.replayed,
        "member_count": len(result.approvals),
        "approvals": [
            {
                "approval_id": str(approval.approval_id),
                "mission_id": str(approval.mission_id),
                "task_id": _uuid_or_none(approval.task_id),
                "approval_type": approval.approval_type,
                "status": approval.status,
                "decided_by": _uuid_or_none(approval.decided_by),
                "decided_at": (
                    None
                    if approval.decided_at is None
                    else approval.decided_at.isoformat()
                ),
                "rationale": approval.rationale,
            }
            for approval in result.approvals
        ],
    }


def budget_request_payload(result: BudgetRequest) -> dict[str, object]:
    """JSON-able BudgetRequest outcome: the durable Approval handle plus
    the exact requested ceiling, all UUIDs stringified."""
    return {
        "approval_id": str(result.approval.approval_id),
        "mission_id": str(result.approval.mission_id),
        "task_id": _uuid_or_none(result.task_id),
        "status": result.approval.status,
        "requested_by": str(result.approval.requested_by),
        "requested_max_tokens": _int_or_none(result.requested_max_tokens),
        "requested_max_tool_calls": _int_or_none(result.requested_max_tool_calls),
        "reason": result.reason,
        "expires_at": (
            None
            if result.approval.expires_at is None
            else result.approval.expires_at.isoformat()
        ),
    }


def budget_decision_payload(result: BudgetDecision) -> dict[str, object]:
    """JSON-able BudgetDecision outcome: the decided approval plus, on
    grant, the new ACTIVE plan carrying the raised ceiling."""
    plan = result.plan
    budget = result.budget
    return {
        "approval_id": str(result.approval.approval_id),
        "mission_id": str(result.approval.mission_id),
        "task_id": _uuid_or_none(result.approval.task_id),
        "granted": result.granted,
        "status": result.approval.status,
        "plan_id": _uuid_or_none(plan.plan_id if plan is not None else None),
        "granted_max_tokens": _int_or_none(budget.max_tokens if budget else None),
        "granted_max_tool_calls": _int_or_none(
            budget.max_tool_calls if budget else None
        ),
    }


class GatewayCommandService:
    """Composes session authorization, project authorization, the idempotency
    ledger and domain dispatch into one command-acceptance path (Chapter
    15.1, 15.2, 15.3)."""

    def __init__(
        self,
        engine: AsyncEngine,
        sessions: GatewaySessionService | None = None,
        dispatcher: CommandDispatcher | None = None,
        ledger: CommandLedger | None = None,
        projections: MissionControlService | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = sessions or GatewaySessionService(engine)
        self._dispatcher = dispatcher or CommandDispatcher(engine)
        self._ledger = ledger or CommandLedger(engine)
        self._projections = projections or MissionControlService(engine)

    async def accept(self, *, command: Command) -> CommandAcceptance:
        if command.client_session_id is None:
            raise DdeError(
                "SESSION_EXPIRED",
                "client_session_id is required to authorize a command",
            )
        scope = required_scope(command.command_type)
        session = await self._sessions.authorize_scope(
            session_id=command.client_session_id,
            principal_id=command.principal_id,
            required_scope=scope,
        )
        project_id = await self._resolve_project(command, session)
        request_hash = _hash_command(command)
        record, is_new = await self._ledger.begin(
            tenant_id=session.tenant_id,
            project_id=project_id,
            idempotency_key=command.idempotency_key,
            request_hash=request_hash,
        )
        if not is_new:
            return self._replay(command, record.status, record.result)
        try:
            acceptance = await self._dispatcher.dispatch(
                command=command,
                tenant_id=session.tenant_id,
                project_id=project_id,
            )
        except DdeError:
            await self._ledger.fail(
                tenant_id=session.tenant_id,
                project_id=project_id,
                command_id=record.command_id,
            )
            raise
        await self._ledger.complete(
            tenant_id=session.tenant_id,
            project_id=project_id,
            command_id=record.command_id,
            result={
                "target_type": acceptance.target_type,
                "target_id": str(acceptance.target_id),
                "payload": acceptance.payload,
            },
        )
        return acceptance

    async def read_mission(
        self, *, session_id: UUID, principal_id: UUID, mission_id: UUID
    ) -> Mission:
        session = await self._sessions.authorize_scope(
            session_id=session_id,
            principal_id=principal_id,
            required_scope="mission.read",
        )
        mission = await self._dispatcher.load_mission(mission_id)
        if mission.tenant_id != session.tenant_id:
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "Mission belongs to another tenant",
                details={"mission_id": str(mission_id)},
            )
        await self._sessions.authorize_project(session, mission.project_id)
        return mission

    async def read_task(
        self, *, session_id: UUID, principal_id: UUID, task_id: UUID
    ) -> Task:
        """Chapter 15.4 task read — authorized via `mission.read` until a
        dedicated `task.read` baseline scope lands (DDE-051 tenancy)."""
        session = await self._sessions.authorize_scope(
            session_id=session_id,
            principal_id=principal_id,
            required_scope="mission.read",
        )
        task = await self._dispatcher.load_task(task_id)
        if task.tenant_id != session.tenant_id:
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "Task belongs to another tenant",
                details={"task_id": str(task_id)},
            )
        await self._sessions.authorize_project(session, task.project_id)
        return task

    async def read_task_graph(
        self, *, session_id: UUID, principal_id: UUID, graph_id: UUID
    ) -> TaskGraph:
        """Chapter 15.4 task-graph read — authorized via `mission.read` until
        `plan.read` is in the human baseline scopes."""
        session = await self._sessions.authorize_scope(
            session_id=session_id,
            principal_id=principal_id,
            required_scope="mission.read",
        )
        graph = await self._dispatcher.load_task_graph(graph_id)
        if graph.tenant_id != session.tenant_id:
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "Task graph belongs to another tenant",
                details={"graph_id": str(graph_id)},
            )
        await self._sessions.authorize_project(session, graph.project_id)
        return graph

    async def read_mission_control(
        self, *, session_id: UUID, principal_id: UUID, mission_id: UUID
    ) -> MissionControl:
        """Operational projection (Chapter 15.4 `GET /v1/mission-control/{id}`).

        Authorizes `mission.read` on the session, verifies the mission belongs
        to the session's tenant, then authorizes the principal for the mission's
        project before building the read model — the same fail-closed order as
        `read_mission`.
        """
        session = await self._sessions.authorize_scope(
            session_id=session_id,
            principal_id=principal_id,
            required_scope="mission.read",
        )
        mission = await self._dispatcher.load_mission(mission_id)
        if mission.tenant_id != session.tenant_id:
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "Mission belongs to another tenant",
                details={"mission_id": str(mission_id)},
            )
        await self._sessions.authorize_project(session, mission.project_id)
        return await self._projections.project(
            tenant_id=session.tenant_id,
            project_id=mission.project_id,
            mission_id=mission_id,
        )

    async def _resolve_project(self, command: Command, session: ClientSession) -> UUID:
        expected = required_target_type(command.command_type)
        if command.target_type != expected:
            raise DdeError(
                "FORBIDDEN",
                f"{command.command_type} requires target_type '{expected}'",
                details={"target_type": command.target_type},
            )
        if command.target_type == "device":
            # Device commands address the bound device; the ledger still
            # needs a project scope (Ch.13.9). Caller supplies project_id
            # in parameters; target_id must match the session's device_id.
            if session.device_id is None or command.target_id != session.device_id:
                raise DdeError(
                    "FORBIDDEN",
                    "device target_id must match the session device_id",
                    details={
                        "target_id": str(command.target_id),
                        "device_id": (
                            None
                            if session.device_id is None
                            else str(session.device_id)
                        ),
                    },
                )
            project_id = _required_uuid_param(command.parameters, "project_id")
            await self._sessions.authorize_project(session, project_id)
            return project_id
        if command.target_type == "project":
            project_id = command.target_id
        else:
            mission = await self._dispatcher.load_mission(command.target_id)
            if mission.tenant_id != session.tenant_id:
                raise DdeError(
                    "TENANT_SCOPE_VIOLATION",
                    "Mission belongs to another tenant",
                    details={"mission_id": str(command.target_id)},
                )
            project_id = mission.project_id
        await self._sessions.authorize_project(session, project_id)
        return project_id

    def _replay(
        self,
        command: Command,
        status: str,
        result: dict[str, object] | None,
    ) -> CommandAcceptance:
        """Replay keeps the CLIENT-facing identity stable: the first
        acceptance echoed `command.command_id`, so a true retry of the same
        body sees the same acceptance shape (the ledger's internal
        `command_id` is storage identity, not part of the 202 contract)."""
        if status == "completed" and result is not None:
            return CommandAcceptance(
                command_id=command.command_id,
                status="completed",
                target_type=str(result["target_type"]),
                target_id=UUID(str(result["target_id"])),
                payload=result["payload"]
                if isinstance(result["payload"], dict)
                else {},
            )
        return CommandAcceptance(
            command_id=command.command_id,
            status=status,
            target_type=command.target_type,
            target_id=command.target_id,
            payload={},
        )
