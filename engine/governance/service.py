"""Production Chapter 13.1–13.4 writer for `approvals`,
`standing_approvals`, and `attention_items` (Chapter 3.8: Approval owner
is `governance`).

This module does not write `missions`/`tasks` rows. Non-blocking
BLOCKED_ON_DECISION / PARTIAL / parking transitions are driven by
`MissionWorkflowService.request_approval` and `expire_and_park`, which
compose this service with `MissionService` under one unit of work
(Chapter 3.5). Governance must not import `engine.missions` — planning
already consults this module, and a cycle would invent a second owner.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.approval import Approval
from engine.contracts.attention_item import AttentionItem
from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.standing_approval import StandingApproval
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.governance.hashing import approval_scope_hash
from engine.governance.repository import (
    ApprovalRepository,
    AttentionItemRepository,
    StandingApprovalRepository,
)
from engine.governance.states import APPROVAL_TRANSITIONS, STANDING_TRANSITIONS
from engine.governance.types import (
    APPROVAL_TTL_HOURS,
    APPROVAL_TYPES,
    ATTENTION_SLA_HOURS,
    BLAST_ORDER,
    DEFAULT_REQUIRED_ROLE,
    OPEN_APPROVAL_STATUSES,
    RISK_ORDER,
    STANDING_FORBIDDEN_TYPES,
    USABLE_APPROVAL_STATUSES,
)
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")

POLICY_VERSION = "governance-approvals-v1"


class ApprovalService:
    """Sole writer of `approvals` / `standing_approvals` / `attention_items`."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        commands: CommandLedger | None = None,
        approvals: ApprovalRepository | None = None,
        standing: StandingApprovalRepository | None = None,
        attention: AttentionItemRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
        self._approvals = approvals or ApprovalRepository()
        self._standing = standing or StandingApprovalRepository()
        self._attention = attention or AttentionItemRepository()
        self._clock = clock or SystemClock()

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
            result = await body(owned)
            await owned.commit()
            return result

    def _replay_approval(self, record: CommandIdempotency) -> Approval:
        if record.status == "completed" and record.result is not None:
            return Approval.model_validate(record.result)
        if record.status == "failed":
            raise DdeError(
                "VERSION_CONFLICT",
                "Command previously failed; refusing to re-execute",
                details={"idempotency_key": record.idempotency_key},
            )
        raise DdeError(
            "VERSION_CONFLICT",
            "Command is already in progress",
            retryable=True,
            details={"idempotency_key": record.idempotency_key},
        )

    def _replay_standing(self, record: CommandIdempotency) -> StandingApproval:
        if record.status == "completed" and record.result is not None:
            return StandingApproval.model_validate(record.result)
        if record.status == "failed":
            raise DdeError(
                "VERSION_CONFLICT",
                "Command previously failed; refusing to re-execute",
                details={"idempotency_key": record.idempotency_key},
            )
        raise DdeError(
            "VERSION_CONFLICT",
            "Command is already in progress",
            retryable=True,
            details={"idempotency_key": record.idempotency_key},
        )

    async def request(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        approval_type: str,
        scope_hash: str,
        requested_by: UUID,
        idempotency_key: str,
        task_id: UUID | None = None,
        required_role: str = DEFAULT_REQUIRED_ROLE,
        evidence_refs: list[str] | None = None,
        suggested_decision: str | None = None,
        standing_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> Approval:
        if approval_type not in APPROVAL_TYPES:
            raise DdeError(
                "POLICY_DENIED",
                f"Unknown approval_type {approval_type!r}",
                retryable=False,
                details={"approval_type": approval_type},
            )

        async def _op(active: PostgresUnitOfWork) -> Approval:
            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=scope_hash,
                uow=active,
            )
            if not is_new:
                return self._replay_approval(record)
            now = self._clock.now()
            approval = Approval(
                approval_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
                approval_type=approval_type,
                scope_hash=scope_hash,
                requested_by=requested_by,
                required_role=required_role,
                evidence_refs=list(evidence_refs or []),
                suggested_decision=suggested_decision,
                status="REQUESTED",
                decided_by=None,
                decided_at=None,
                expires_at=now + timedelta(hours=APPROVAL_TTL_HOURS),
                rationale=None,
                standing_id=standing_id,
                edr_id=None,
                human_minutes=0.0,
                command_id=record.command_id,
                created_at=now,
                updated_at=now,
            )
            await self._approvals.insert(active.connection, approval)
            await self._raise_attention(
                active,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                kind="approval_requested",
                summary=f"{approval_type} approval requested",
                approval_id=approval.approval_id,
            )
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ApprovalRequested",
                aggregate_type="approval",
                aggregate_id=approval.approval_id,
                mission_id=mission_id,
                task_id=task_id,
                payload={
                    "approval_type": approval_type,
                    "scope_hash": scope_hash,
                    "status": approval.status,
                },
                uow=active,
            )
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=approval.model_dump(mode="json"),
                uow=active,
            )
            return approval

        return await self._run(uow, tenant_id, project_id, _op)

    async def decide(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        approval_id: UUID,
        decision: str,
        decided_by: UUID,
        rationale: str,
        scope_hash: str,
        human_minutes: float = 0.0,
        edr_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> Approval:
        if decision not in {"APPROVED", "REJECTED"}:
            raise DdeError(
                "POLICY_DENIED",
                "decide() accepts only APPROVED or REJECTED",
                retryable=False,
                details={"decision": decision},
            )

        async def _op(active: PostgresUnitOfWork) -> Approval:
            current = await self._require_approval(active, approval_id)
            if current.scope_hash != scope_hash:
                raise DdeError(
                    "POLICY_DENIED",
                    "Approval cannot be reused for a materially different plan",
                    retryable=False,
                    details={
                        "approval_id": str(approval_id),
                        "bound_scope_hash": current.scope_hash,
                        "presented_scope_hash": scope_hash,
                    },
                )
            now = self._clock.now()
            if current.expires_at is not None and current.expires_at <= now:
                raise DdeError(
                    "POLICY_DENIED",
                    "Approval has expired",
                    retryable=False,
                    details={"approval_id": str(approval_id)},
                )
            next_status = transition(current.status, decision, APPROVAL_TRANSITIONS)
            await self._approvals.update_fields(
                active.connection,
                approval_id,
                fields={
                    "status": next_status,
                    "decided_by": decided_by,
                    "decided_at": now,
                    "rationale": rationale,
                    "edr_id": edr_id,
                    "human_minutes": human_minutes,
                    "updated_at": now,
                },
            )
            updated = await self._require_approval(active, approval_id)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ApprovalDecided",
                aggregate_type="approval",
                aggregate_id=approval_id,
                mission_id=updated.mission_id,
                task_id=updated.task_id,
                payload={
                    "status": updated.status,
                    "scope_hash": updated.scope_hash,
                    "edr_id": None if edr_id is None else str(edr_id),
                },
                uow=active,
            )
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def expire(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        approval_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> Approval:
        async def _op(active: PostgresUnitOfWork) -> Approval:
            current = await self._require_approval(active, approval_id)
            now = self._clock.now()
            if current.expires_at is not None and current.expires_at > now:
                raise DdeError(
                    "POLICY_DENIED",
                    "Approval has not reached expires_at",
                    retryable=False,
                    details={"approval_id": str(approval_id)},
                )
            next_status = transition(current.status, "EXPIRED", APPROVAL_TRANSITIONS)
            await self._approvals.update_fields(
                active.connection,
                approval_id,
                fields={"status": next_status, "updated_at": now},
            )
            updated = await self._require_approval(active, approval_id)
            await self._raise_attention(
                active,
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=updated.mission_id,
                kind="expired_approval",
                summary="approval expired; mission must park",
                approval_id=approval_id,
            )
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="ApprovalExpired",
                aggregate_type="approval",
                aggregate_id=approval_id,
                mission_id=updated.mission_id,
                task_id=updated.task_id,
                payload={"status": updated.status},
                uow=active,
            )
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def withdraw(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        approval_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> Approval:
        async def _op(active: PostgresUnitOfWork) -> Approval:
            current = await self._require_approval(active, approval_id)
            now = self._clock.now()
            next_status = transition(current.status, "WITHDRAWN", APPROVAL_TRANSITIONS)
            await self._approvals.update_fields(
                active.connection,
                approval_id,
                fields={"status": next_status, "updated_at": now},
            )
            return await self._require_approval(active, approval_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def require_approved(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        scope_hash: str,
        approval_type: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> Approval:
        """Fail-closed gate used by production mutation sites."""

        async def _op(active: PostgresUnitOfWork) -> Approval:
            found = await self._approvals.get_approved_by_scope_hash(
                active.connection, scope_hash, approval_type
            )
            now = self._clock.now()
            if (
                found is None
                or found.approval_type != approval_type
                or found.status not in USABLE_APPROVAL_STATUSES
                or (found.expires_at is not None and found.expires_at <= now)
            ):
                raise DdeError(
                    "POLICY_DENIED",
                    "Required approval is missing, expired, or bound to a "
                    "different plan",
                    retryable=False,
                    details={
                        "scope_hash": scope_hash,
                        "approval_type": approval_type,
                        "status": None if found is None else found.status,
                    },
                )
            return found

        return await self._run(uow, tenant_id, project_id, _op)

    async def has_approved(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        scope_hash: str,
        approval_type: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> bool:
        try:
            await self.require_approved(
                tenant_id=tenant_id,
                project_id=project_id,
                scope_hash=scope_hash,
                approval_type=approval_type,
                uow=uow,
            )
        except DdeError as exc:
            if exc.error_code == "POLICY_DENIED":
                return False
            raise
        return True

    async def grant_standing(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        approval_types: list[str],
        blast_radius_ceiling: str,
        risk_ceiling: str,
        cost_ceiling: float,
        task_count_ceiling: int,
        path_scope: list[str],
        forbidden_operations: list[str],
        valid_from_hours: float,
        valid_until_hours: float,
        granted_by: UUID,
        rationale: str,
        idempotency_key: str,
        mission_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> StandingApproval:
        unknown = [item for item in approval_types if item not in APPROVAL_TYPES]
        if unknown:
            raise DdeError(
                "POLICY_DENIED",
                "Standing approval_types contains an unknown class",
                retryable=False,
                details={"unknown": unknown},
            )
        forbidden = [
            item for item in approval_types if item in STANDING_FORBIDDEN_TYPES
        ]
        if forbidden:
            raise DdeError(
                "POLICY_DENIED",
                "A standing approval can never pre-authorise this approval_type",
                retryable=False,
                details={"forbidden": forbidden},
            )
        if risk_ceiling == "critical":
            raise DdeError(
                "POLICY_DENIED",
                "A standing approval can never pre-authorise a critical risk action",
                retryable=False,
            )
        if blast_radius_ceiling not in BLAST_ORDER or risk_ceiling not in RISK_ORDER:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown blast_radius_ceiling or risk_ceiling",
                retryable=False,
            )
        digest = approval_scope_hash(
            approval_type="standing",
            mission_id=mission_id or project_id,
            payload={
                "approval_types": sorted(approval_types),
                "path_scope": path_scope,
                "valid_until_hours": valid_until_hours,
            },
        )

        async def _op(active: PostgresUnitOfWork) -> StandingApproval:
            record, is_new = await self._commands.begin(
                tenant_id=tenant_id,
                project_id=project_id,
                idempotency_key=idempotency_key,
                request_hash=digest,
                uow=active,
            )
            if not is_new:
                return self._replay_standing(record)
            now = self._clock.now()
            standing = StandingApproval(
                standing_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                approval_types=list(approval_types),
                blast_radius_ceiling=blast_radius_ceiling,
                risk_ceiling=risk_ceiling,
                cost_ceiling=cost_ceiling,
                task_count_ceiling=task_count_ceiling,
                path_scope=list(path_scope),
                forbidden_operations=list(
                    {*forbidden_operations, "IRREVERSIBLE", "production_change"}
                ),
                valid_from=now + timedelta(hours=valid_from_hours),
                valid_until=now + timedelta(hours=valid_until_hours),
                revocable_immediately=True,
                granted_by=granted_by,
                rationale=rationale,
                status="ACTIVE",
                task_count_used=0,
                cost_used=0.0,
                revoked_at=None,
                command_id=record.command_id,
                created_at=now,
                updated_at=now,
            )
            await self._standing.insert(active.connection, standing)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="StandingApprovalGranted",
                aggregate_type="standing_approval",
                aggregate_id=standing.standing_id,
                mission_id=mission_id,
                payload={"approval_types": standing.approval_types},
                uow=active,
            )
            await self._commands.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                command_id=record.command_id,
                result=standing.model_dump(mode="json"),
                uow=active,
            )
            return standing

        return await self._run(uow, tenant_id, project_id, _op)

    async def revoke_standing(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        standing_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> StandingApproval:
        async def _op(active: PostgresUnitOfWork) -> StandingApproval:
            current = await self._require_standing(active, standing_id)
            now = self._clock.now()
            next_status = transition(current.status, "REVOKED", STANDING_TRANSITIONS)
            await self._standing.update_fields(
                active.connection,
                standing_id,
                fields={
                    "status": next_status,
                    "revoked_at": now,
                    "updated_at": now,
                },
            )
            updated = await self._require_standing(active, standing_id)
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="StandingApprovalRevoked",
                aggregate_type="standing_approval",
                aggregate_id=standing_id,
                mission_id=updated.mission_id,
                payload={"status": updated.status},
                uow=active,
            )
            return updated

        return await self._run(uow, tenant_id, project_id, _op)

    async def authorize_standing(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        standing_id: UUID,
        approval_type: str,
        scope_hash: str,
        requested_by: UUID,
        mission_id: UUID,
        mission_scope: list[str],
        requested_paths: list[str],
        risk_class: str,
        blast_radius: str,
        cost: float = 0.0,
        operation: str = "",
        task_id: UUID | None = None,
        idempotency_key: str,
        uow: PostgresUnitOfWork | None = None,
    ) -> Approval:
        """Mint an already-APPROVED Approval under standing authority, or
        fail closed. Records standing_id on the approval (Chapter 13.2)."""

        async def _op(active: PostgresUnitOfWork) -> Approval:
            standing = await self._require_standing(active, standing_id)
            now = self._clock.now()
            self._assert_standing_covers(
                standing,
                approval_type=approval_type,
                mission_id=mission_id,
                mission_scope=mission_scope,
                requested_paths=requested_paths,
                risk_class=risk_class,
                blast_radius=blast_radius,
                cost=cost,
                operation=operation,
                now=now,
            )
            minted = await self.request(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                approval_type=approval_type,
                scope_hash=scope_hash,
                requested_by=requested_by,
                idempotency_key=idempotency_key,
                task_id=task_id,
                standing_id=standing_id,
                uow=active,
            )
            decided = await self.decide(
                tenant_id=tenant_id,
                project_id=project_id,
                approval_id=minted.approval_id,
                decision="APPROVED",
                decided_by=standing.granted_by,
                rationale=f"standing:{standing.standing_id}",
                scope_hash=scope_hash,
                human_minutes=0.0,
                uow=active,
            )
            await self._standing.update_fields(
                active.connection,
                standing_id,
                fields={
                    "task_count_used": standing.task_count_used + 1,
                    "cost_used": float(standing.cost_used) + cost,
                    "updated_at": now,
                },
            )
            return decided

        return await self._run(uow, tenant_id, project_id, _op)

    def _assert_standing_covers(
        self,
        standing: StandingApproval,
        *,
        approval_type: str,
        mission_id: UUID,
        mission_scope: list[str],
        requested_paths: list[str],
        risk_class: str,
        blast_radius: str,
        cost: float,
        operation: str,
        now: datetime,
    ) -> None:
        if standing.status != "ACTIVE":
            raise DdeError(
                "POLICY_DENIED",
                "Standing approval is not ACTIVE",
                retryable=False,
                details={"status": standing.status},
            )
        if now < standing.valid_from or now > standing.valid_until:
            raise DdeError(
                "POLICY_DENIED",
                "Standing approval is outside its valid window",
                retryable=False,
            )
        if standing.mission_id is not None and standing.mission_id != mission_id:
            raise DdeError(
                "POLICY_DENIED",
                "Standing approval is bound to a different mission",
                retryable=False,
            )
        if approval_type in STANDING_FORBIDDEN_TYPES:
            raise DdeError(
                "POLICY_DENIED",
                "A standing approval can never pre-authorise this approval_type",
                retryable=False,
                details={"approval_type": approval_type},
            )
        if approval_type not in standing.approval_types:
            raise DdeError(
                "POLICY_DENIED",
                "Standing approval does not cover this approval_type",
                retryable=False,
            )
        if risk_class == "critical" or RISK_ORDER.get(risk_class, 99) > RISK_ORDER.get(
            standing.risk_ceiling, -1
        ):
            raise DdeError(
                "POLICY_DENIED",
                "Standing approval risk_ceiling exceeded",
                retryable=False,
                details={"risk_class": risk_class, "ceiling": standing.risk_ceiling},
            )
        if BLAST_ORDER.get(blast_radius, 99) > BLAST_ORDER.get(
            standing.blast_radius_ceiling, -1
        ):
            raise DdeError(
                "POLICY_DENIED",
                "Standing approval blast_radius_ceiling exceeded",
                retryable=False,
            )
        if standing.task_count_used >= standing.task_count_ceiling:
            raise DdeError(
                "POLICY_DENIED",
                "Standing approval task_count_ceiling exceeded",
                retryable=False,
            )
        if float(standing.cost_used) + cost > float(standing.cost_ceiling):
            raise DdeError(
                "POLICY_DENIED",
                "Standing approval cost_ceiling exceeded",
                retryable=False,
            )
        if operation and operation in standing.forbidden_operations:
            raise DdeError(
                "POLICY_DENIED",
                "Standing approval forbids this operation",
                retryable=False,
                details={"operation": operation},
            )
        for path in requested_paths:
            if not _path_in_scope(path, standing.path_scope):
                raise DdeError(
                    "POLICY_DENIED",
                    "Requested path is outside standing path_scope",
                    retryable=False,
                    details={"path": path},
                )
            if approval_type == "scope_widening" and not _path_in_scope(
                path, mission_scope
            ):
                raise DdeError(
                    "POLICY_DENIED",
                    "Standing approval cannot pre-authorise a scope widening "
                    "beyond the mission's declared scope",
                    retryable=False,
                    details={"path": path},
                )

    async def attention_budget(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> dict[str, object]:
        """Chapter 13.4 metrics derived from durable rows, not estimates."""

        async def _op(active: PostgresUnitOfWork) -> dict[str, object]:
            rows = await self._approvals.list_for_mission(active.connection, mission_id)
            items = await self._attention.list_for_mission(
                active.connection, mission_id
            )
            now = self._clock.now()
            human_minutes = sum(float(item.human_minutes) for item in rows)
            open_items = [item for item in items if item.status == "OPEN"]
            debt = [item for item in open_items if item.sla_due_at <= now]
            standing_uses = [item for item in rows if item.standing_id is not None]
            return {
                "human_minutes": human_minutes,
                "approvals_per_mission": len(rows),
                "approvals_by_type": _count_by(rows, "approval_type"),
                "attention_debt": len(debt),
                "open_attention_items": len(open_items),
                "standing_approval_usage": len(standing_uses),
                "blocked_requests": sum(
                    1 for item in rows if item.status in OPEN_APPROVAL_STATUSES
                ),
            }

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_attention(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[AttentionItem]:
        async def _op(active: PostgresUnitOfWork) -> list[AttentionItem]:
            return await self._attention.list_for_mission(active.connection, mission_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def get_approval(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        approval_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> Approval:
        async def _op(active: PostgresUnitOfWork) -> Approval:
            return await self._require_approval(active, approval_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def _raise_attention(
        self,
        active: PostgresUnitOfWork,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        kind: str,
        summary: str,
        approval_id: UUID | None = None,
        standing_id: UUID | None = None,
    ) -> AttentionItem:
        now = self._clock.now()
        item = AttentionItem(
            attention_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            kind=kind,
            summary=summary,
            status="OPEN",
            approval_id=approval_id,
            standing_id=standing_id,
            sla_due_at=now + timedelta(hours=ATTENTION_SLA_HOURS),
            opened_at=now,
            acknowledged_at=None,
            created_at=now,
            updated_at=now,
        )
        await self._attention.insert(active.connection, item)
        return item

    async def _require_approval(
        self, active: PostgresUnitOfWork, approval_id: UUID
    ) -> Approval:
        record = await self._approvals.get_by_id(active.connection, approval_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown approval")
        return record

    async def _require_standing(
        self, active: PostgresUnitOfWork, standing_id: UUID
    ) -> StandingApproval:
        record = await self._standing.get_by_id(active.connection, standing_id)
        if record is None:
            raise DdeError("POLICY_DENIED", "Unknown standing approval")
        return record


def _path_in_scope(path: str, scope: list[str]) -> bool:
    """Chapter 4.5 rule 3 prefix check.

    Duplicated from `engine.planning.validate.in_scope` because this
    module must not import `engine.planning` — `TaskGraphService` already
    imports `ApprovalService`, and a package-level import would cycle.
    """
    normalised = path.replace("\\", "/").rstrip("/")
    for item in scope:
        prefix = item.replace("\\", "/").rstrip("/")
        if normalised == prefix or normalised.startswith(f"{prefix}/"):
            return True
    return False


def _count_by(rows: list[Approval], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(getattr(row, field))
        counts[key] = counts.get(key, 0) + 1
    return counts
