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

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TypeVar, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.audit.service import AuditService
from engine.contracts.approval import Approval
from engine.contracts.attention_item import AttentionItem
from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.execution_plan import ExecutionPlan
from engine.contracts.standing_approval import StandingApproval
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.execution.hashing import plan_hash
from engine.execution.repository import ExecutionPlanRepository
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
    BUDGET_MAX_TOKENS_KEY,
    BUDGET_MAX_TOOL_CALLS_KEY,
    DEFAULT_REQUIRED_ROLE,
    OPEN_APPROVAL_STATUSES,
    RISK_ORDER,
    STANDING_FORBIDDEN_TYPES,
    USABLE_APPROVAL_STATUSES,
)
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work
from engine.workers.budget import (
    AttemptBudget,
    attempt_budget_from_plan,
    attempt_budget_json,
)

T = TypeVar("T")

POLICY_VERSION = "governance-approvals-v1"

#: Event-store type appended when one batch command records decisions for
#: several approvals (Chapter 13.1 batch-approve amendment).
BATCH_DECIDED_EVENT_TYPE = "ApprovalBatchDecided"

#: Event-store type appended when a human grants or denies a budget
#: increase request (Ch.7.1/12.3 pause-for-human path).
BUDGET_DECIDED_EVENT_TYPE = "BudgetIncreaseDecided"


@dataclass(frozen=True)
class BatchDecisionResult:
    """Outcome of one all-or-nothing `batch_decide` command: every member
    approval in its post-decision state, plus the batch's own durable
    identity. `replayed` marks a repeat call that returned the first
    command's stored outcome instead of re-deciding."""

    batch_id: UUID | None
    approvals: list[Approval]
    decided_by: UUID
    decision: str
    created_at: datetime
    replayed: bool = False


@dataclass(frozen=True)
class BudgetRequest:
    """The durable handle on the budget-increase workflow: an ordinary
    Chapter 13.1 Approval (`approval_type="budget_increase"`) whose
    scope_hash binds it to exactly one paused task and one requested
    ceiling."""

    approval: Approval
    task_id: UUID | None
    requested_max_tokens: int | None = None
    requested_max_tool_calls: int | None = None
    reason: str = ""


@dataclass(frozen=True)
class BudgetDecision:
    """Outcome of granting/denying a budget-increase request. On grant,
    `plan` is the new immutable ExecutionPlan carrying the raised ceiling;
    on denial it is `None` and nothing was widened."""

    approval: Approval
    granted: bool
    plan: ExecutionPlan | None = None
    budget: AttemptBudget | None = None


def _decision_audit_payload(
    approval: Approval,
    *,
    decided_by: UUID,
    decision: str,
    batch_id: UUID | None,
    idempotency_key: str | None,
) -> dict[str, object]:
    """The durable, restart-readable audit trail of one human decision.

    Chapter 14.5 invariant 9: every security-relevant decision produces an
    `audit_event`. Payload carries identity, not narration: who decided
    which bound scope, when, under which command/batch, with what
    rationale and human-minutes cost (Chapter 13.4)."""
    return {
        "approval_id": str(approval.approval_id),
        "mission_id": str(approval.mission_id),
        "task_id": None if approval.task_id is None else str(approval.task_id),
        "approval_type": approval.approval_type,
        "scope_hash": approval.scope_hash,
        "decision": decision,
        "status": approval.status,
        "decided_by": str(decided_by),
        "decided_at": (
            None if approval.decided_at is None else approval.decided_at.isoformat()
        ),
        "rationale": approval.rationale,
        "human_minutes": float(approval.human_minutes),
        "standing_id": (
            None if approval.standing_id is None else str(approval.standing_id)
        ),
        "edr_id": None if approval.edr_id is None else str(approval.edr_id),
        "batch_id": None if batch_id is None else str(batch_id),
        "idempotency_key": idempotency_key,
    }


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
        audit: AuditService | None = None,
        plans: ExecutionPlanRepository | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
        self._approvals = approvals or ApprovalRepository()
        self._standing = standing or StandingApprovalRepository()
        self._attention = attention or AttentionItemRepository()
        # Read/insert access to `execution_plans` for the budget-increase
        # grant path only; `engine.execution` remains the sole writer of
        # plans produced by planning itself.
        self._plans = plans or ExecutionPlanRepository()
        self._clock = clock or SystemClock()
        # Sole writer of the hash-chained `audit_events` ledger; governance
        # composes it into its own transactions and never writes those rows
        # itself.
        self._audit = audit or AuditService(engine, clock=self._clock)

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
        batch_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> Approval:
        """Record one human decision. `batch_id` is set only by
        `batch_decide`, which passes its command identity down so every
        member's audit entry records the batch that decided it."""
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
            await self._audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="approval.decided",
                payload=_decision_audit_payload(
                    updated,
                    decided_by=decided_by,
                    decision=decision,
                    batch_id=batch_id,
                    idempotency_key=None,
                ),
                uow=active,
            )
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

    async def batch_decide(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        approval_ids: list[UUID],
        decision: str,
        decided_by: UUID,
        rationale: str,
        scope_hashes: list[str],
        human_minutes: float = 0.0,
        edr_id: UUID | None = None,
        idempotency_key: str | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> BatchDecisionResult:
        """Chapter 13.1 batch-approve amendment: decide several pending
        approvals as ONE all-or-nothing command -- every approval in the
        batch records its decision or none does; a partial batch is never
        committed. Each member obeys the same scope_hash binding, expiry
        and state-machine rules as a single `decide`, so one bad member
        aborts the whole batch rather than being skipped. The batch itself
        is one auditable command with its own idempotency key (Chapter
        12.5): a replay returns the first outcome without re-deciding."""

        if len(approval_ids) == 0:
            raise DdeError(
                "POLICY_DENIED",
                "A batch must name at least one approval",
                retryable=False,
            )
        if len(approval_ids) != len(scope_hashes):
            raise DdeError(
                "POLICY_DENIED",
                "scope_hashes must be parallel to approval_ids",
                retryable=False,
                details={
                    "approval_ids": len(approval_ids),
                    "scope_hashes": len(scope_hashes),
                },
            )
        if len(set(approval_ids)) != len(approval_ids):
            raise DdeError(
                "POLICY_DENIED",
                "A batch may not name the same approval twice",
                retryable=False,
            )
        if decision not in {"APPROVED", "REJECTED"}:
            raise DdeError(
                "POLICY_DENIED",
                "batch_decide accepts only APPROVED or REJECTED",
                retryable=False,
                details={"decision": decision},
            )

        request_hash = sha256_hex(
            canonical_json(
                {
                    "command": "batch_decide",
                    "approval_ids": [str(item) for item in approval_ids],
                    "scope_hashes": list(scope_hashes),
                    "decision": decision,
                    "decided_by": str(decided_by),
                    "edr_id": None if edr_id is None else str(edr_id),
                }
            )
        )
        now = self._clock.now()

        async def _op(
            active: PostgresUnitOfWork,
        ) -> tuple[BatchDecisionResult, UUID | None]:
            batch_id: UUID | None = None
            if idempotency_key is not None:
                record, is_new = await self._commands.begin(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    uow=active,
                )
                if not is_new:
                    return self._replay_batch(record), None
                batch_id = record.command_id

            for index, approval_id in enumerate(approval_ids):
                await self.decide(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    approval_id=approval_id,
                    decision=decision,
                    decided_by=decided_by,
                    rationale=rationale,
                    scope_hash=scope_hashes[index],
                    human_minutes=human_minutes,
                    edr_id=edr_id,
                    batch_id=batch_id,
                    uow=active,
                )

            decided = [
                await self._require_approval(active, item) for item in approval_ids
            ]
            if batch_id is not None:
                await self._events.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    event_type=BATCH_DECIDED_EVENT_TYPE,
                    aggregate_type="command",
                    aggregate_id=batch_id,
                    mission_id=decided[0].mission_id,
                    task_id=decided[0].task_id,
                    payload={
                        "batch_id": str(batch_id),
                        "decision": decision,
                        "member_count": len(decided),
                        "approval_ids": [str(item) for item in approval_ids],
                    },
                    uow=active,
                )
                await self._commands.complete(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    command_id=batch_id,
                    result=_batch_result_json(decided, batch_id, decided_by),
                    uow=active,
                )
            return (
                BatchDecisionResult(
                    batch_id=batch_id,
                    approvals=decided,
                    decided_by=decided_by,
                    decision=decision,
                    created_at=now,
                ),
                batch_id,
            )

        result, committed_batch_id = await self._run(uow, tenant_id, project_id, _op)
        if committed_batch_id is None and result.batch_id is None:
            # A replayed batch keeps the original command's identity.
            return BatchDecisionResult(
                batch_id=result.batch_id,
                approvals=result.approvals,
                decided_by=result.decided_by,
                decision=result.decision,
                created_at=result.created_at,
                replayed=True,
            )
        return result

    def _replay_batch(self, record: CommandIdempotency) -> BatchDecisionResult:
        if record.status == "completed" and record.result is not None:
            payload = record.result
            approvals = [
                Approval.model_validate(item)
                for item in cast("list[object]", payload["approvals"])
            ]
            return BatchDecisionResult(
                batch_id=UUID(cast("str", payload["batch_id"])),
                approvals=approvals,
                decided_by=UUID(cast("str", payload["decided_by"])),
                decision=approvals[0].status,
                created_at=approvals[0].decided_at or approvals[0].updated_at,
                replayed=True,
            )
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

    async def request_budget_increase(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        requested_by: UUID,
        idempotency_key: str,
        reason: str,
        requested_max_tokens: int | None = None,
        requested_max_tool_calls: int | None = None,
        task_id: UUID | None = None,
        uow: PostgresUnitOfWork | None = None,
    ) -> BudgetRequest:
        """Human-facing budget workflow, request half (Ch.7.1/12.3): when
        a dispatch has been refused by a budget ceiling
        (`BUDGET_EXCEEDED` -> RESOURCE_EXHAUSTION row,
        `requires_human=True`), the human surfaces the decision through an
        ordinary `budget_increase` Approval instead of editing a plan's
        budget by hand. The scope_hash binds the request to exactly one
        task and one requested ceiling; approving it cannot widen any
        other task's budget."""

        if requested_max_tokens is None and requested_max_tool_calls is None:
            raise DdeError(
                "POLICY_DENIED",
                "A budget increase must request at least one concrete "
                "ceiling (tokens or tool calls)",
                retryable=False,
            )
        if reason.strip() == "":
            raise DdeError(
                "POLICY_DENIED",
                "request_budget_increase requires a reason",
                retryable=False,
            )
        if task_id is None:
            raise DdeError(
                "POLICY_DENIED",
                "request_budget_increase binds to exactly one task",
                retryable=False,
            )

        payload = budget_scope_payload(
            requested_max_tokens=requested_max_tokens,
            requested_max_tool_calls=requested_max_tool_calls,
            reason=reason,
        )
        digest = approval_scope_hash(
            approval_type="budget_increase",
            mission_id=mission_id,
            payload=payload,
            task_id=task_id,
        )
        approval = await self.request(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            approval_type="budget_increase",
            scope_hash=digest,
            requested_by=requested_by,
            idempotency_key=idempotency_key,
            task_id=task_id,
            evidence_refs=[reason],
            suggested_decision=_budget_request_json(payload),
            uow=uow,
        )
        return BudgetRequest(
            approval=approval,
            task_id=task_id,
            requested_max_tokens=requested_max_tokens,
            requested_max_tool_calls=requested_max_tool_calls,
            reason=reason,
        )

    async def decide_budget_increase(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        approval_id: UUID,
        decided_by: UUID,
        decision: str,
        rationale: str,
        human_minutes: float = 0.0,
        uow: PostgresUnitOfWork | None = None,
    ) -> BudgetDecision:
        """Human-facing budget workflow, decide half. On APPROVED this
        re-plans the bound ExecutionPlan with the raised ceiling and marks
        the new plan ACTIVE in the same transaction as the decision
        itself -- the grant commits or nothing does. The raised ceiling is
        part of the new immutable plan definition (`token_budget`, hashed
        before persist), so it survives restarts and cannot silently
        widen any other task's budget. Denial records only the
        decision."""

        if decision not in {"APPROVED", "REJECTED"}:
            raise DdeError(
                "POLICY_DENIED",
                "decide_budget_increase accepts only APPROVED or REJECTED",
                retryable=False,
                details={"decision": decision},
            )

        async def _op(active: PostgresUnitOfWork) -> BudgetDecision:
            current = await self._require_approval(active, approval_id)
            if current.approval_type != "budget_increase":
                raise DdeError(
                    "POLICY_DENIED",
                    "decide_budget_increase applies to a budget_increase approval",
                    retryable=False,
                    details={
                        "approval_id": str(approval_id),
                        "approval_type": current.approval_type,
                    },
                )
            if current.task_id is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "budget_increase approval is not bound to a task",
                    retryable=False,
                    details={"approval_id": str(approval_id)},
                )

            granted_plan: ExecutionPlan | None = None
            granted_budget: AttemptBudget | None = None
            next_status = transition(current.status, decision, APPROVAL_TRANSITIONS)
            now = self._clock.now()
            await self._approvals.update_fields(
                active.connection,
                approval_id,
                fields={
                    "status": next_status,
                    "decided_by": decided_by,
                    "decided_at": now,
                    "rationale": rationale,
                    "human_minutes": human_minutes,
                    "updated_at": now,
                },
            )
            updated = await self._require_approval(active, approval_id)

            if decision == "APPROVED":
                (
                    granted_plan,
                    granted_budget,
                ) = await self._grant_budget_ceiling(active, updated)

            requested = _requested_budget_from_payload(
                _budget_request_payload(updated.suggested_decision)
            )
            await self._audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type="approval.decided",
                payload=_decision_audit_payload(
                    updated,
                    decided_by=decided_by,
                    decision=decision,
                    batch_id=None,
                    idempotency_key=None,
                ),
                uow=active,
            )
            await self._events.append(
                tenant_id=tenant_id,
                project_id=project_id,
                event_type=BUDGET_DECIDED_EVENT_TYPE,
                aggregate_type="execution_plan" if granted_plan else "approval",
                aggregate_id=(granted_plan.plan_id if granted_plan else approval_id),
                mission_id=updated.mission_id,
                task_id=updated.task_id,
                payload={
                    "approval_id": str(approval_id),
                    "decision": decision,
                    "granted": granted_plan is not None,
                    "plan_id": (
                        None if granted_plan is None else str(granted_plan.plan_id)
                    ),
                    "requested_max_tokens": requested.max_tokens,
                    "requested_max_tool_calls": requested.max_tool_calls,
                },
                uow=active,
            )
            return BudgetDecision(
                approval=updated,
                granted=granted_plan is not None,
                plan=granted_plan,
                budget=granted_budget,
            )

        return await self._run(uow, tenant_id, project_id, _op)

    async def _grant_budget_ceiling(
        self, active: PostgresUnitOfWork, approval: Approval
    ) -> tuple[ExecutionPlan, AttemptBudget]:
        """Re-plan the bound attempt with the approved ceiling. The old
        plan stays as history; the new plan carries the raised immutable
        definition."""
        task_id = approval.task_id
        if task_id is None:
            raise DdeError(
                "POLICY_DENIED",
                "budget_increase approval is not bound to a task",
                retryable=False,
                details={"approval_id": str(approval.approval_id)},
            )
        plans = await self._plans.list_for_task(active.connection, task_id)
        if not plans:
            raise DdeError(
                "POLICY_DENIED",
                "Cannot grant a budget increase for a task that has no ExecutionPlan",
                retryable=False,
                details={"task_id": str(task_id)},
            )
        latest = plans[-1]
        current_budget = (
            attempt_budget_from_plan(latest.token_budget) or AttemptBudget()
        )
        requested = _requested_budget_from_payload(
            _budget_request_payload(approval.suggested_decision)
        )
        new_budget = AttemptBudget(
            max_tokens=(
                requested.max_tokens
                if requested.max_tokens is not None
                else current_budget.max_tokens
            ),
            max_tool_calls=(
                requested.max_tool_calls
                if requested.max_tool_calls is not None
                else current_budget.max_tool_calls
            ),
        )
        merged_token_budget: dict[str, object] = {
            **latest.token_budget,
            **attempt_budget_json(new_budget),
        }
        now = self._clock.now()
        rehashed = plan_hash(
            tenant_id=latest.tenant_id,
            project_id=latest.project_id,
            mission_id=latest.mission_id,
            task_id=latest.task_id,
            route_decision_id=latest.route_decision_id,
            context_package_id=latest.context_package_id,
            worker_profile_id=latest.worker_profile_id,
            execution_environment_id=latest.execution_environment_id,
            workspace_policy=latest.workspace_policy,
            capability_requirements=latest.capability_requirements,
            enforcement_tier=latest.enforcement_tier,
            autonomy_level=latest.autonomy_level,
            resource_budget=latest.resource_budget,
            time_budget=latest.time_budget,
            token_budget=merged_token_budget,
            network_policy=latest.network_policy,
            filesystem_policy=latest.filesystem_policy,
            checkpoint_policy=latest.checkpoint_policy,
            retry_policy=latest.retry_policy,
            escalation_policy=latest.escalation_policy,
        )
        new_plan = ExecutionPlan(
            plan_id=uuid7(),
            tenant_id=latest.tenant_id,
            project_id=latest.project_id,
            mission_id=latest.mission_id,
            task_id=latest.task_id,
            route_decision_id=latest.route_decision_id,
            context_package_id=latest.context_package_id,
            worker_profile_id=latest.worker_profile_id,
            execution_environment_id=latest.execution_environment_id,
            write_scope_lease_id=latest.write_scope_lease_id,
            workspace_policy=latest.workspace_policy,
            capability_requirements=latest.capability_requirements,
            enforcement_tier=latest.enforcement_tier,
            autonomy_level=latest.autonomy_level,
            resource_budget=latest.resource_budget,
            time_budget=latest.time_budget,
            token_budget=merged_token_budget,
            network_policy=latest.network_policy,
            filesystem_policy=latest.filesystem_policy,
            checkpoint_policy=latest.checkpoint_policy,
            retry_policy=latest.retry_policy,
            escalation_policy=latest.escalation_policy,
            plan_hash=rehashed,
            status="ACTIVE",
            created_at=now,
            updated_at=now,
            approved_at=now,
            started_at=None,
            ended_at=None,
        )
        await self._plans.insert_plan(active.connection, new_plan)
        return new_plan, new_budget

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


def budget_scope_payload(
    *,
    requested_max_tokens: int | None,
    requested_max_tool_calls: int | None,
    reason: str,
) -> dict[str, object]:
    """The payload a `budget_increase` approval's scope_hash binds to:
    the exact requested ceiling and nothing else. Two requests that
    differ only in reason are the same logical grant and may share an
    approval; two requests that differ in ceiling never do."""
    return {
        BUDGET_MAX_TOKENS_KEY: requested_max_tokens,
        BUDGET_MAX_TOOL_CALLS_KEY: requested_max_tool_calls,
        "reason": reason,
    }


def _budget_request_json(payload: dict[str, object]) -> str:
    """Canonical JSON of the request payload, stored in the approval's
    `suggested_decision` so `decide_budget_increase` reads back the exact
    ceiling that was hashed -- never a re-derivation."""
    return canonical_json(payload)


def _budget_request_payload(raw: str | None) -> dict[str, object]:
    try:
        decoded = json.loads(raw or "")
    except json.JSONDecodeError:
        return {}
    if not isinstance(decoded, dict):
        return {}
    return decoded


def _batch_result_json(
    approvals: list[Approval], batch_id: UUID, decided_by: UUID
) -> dict[str, object]:
    """The durable replay record of one completed batch command: the
    post-decision state of every member plus the batch's own identity."""
    return {
        "batch_id": str(batch_id),
        "decided_by": str(decided_by),
        "approvals": [item.model_dump(mode="json") for item in approvals],
    }


def _requested_budget_from_payload(payload: dict[str, object]) -> AttemptBudget:
    """Decode the concrete ceiling out of a budget scope payload.
    Malformed or negative values degrade to absent rather than raising --
    a corrupt historical payload must not turn a human decision into a
    500."""

    def _int(value: object) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return value

    return AttemptBudget(
        max_tokens=_int(payload.get(BUDGET_MAX_TOKENS_KEY)),
        max_tool_calls=_int(payload.get(BUDGET_MAX_TOOL_CALLS_KEY)),
    )
