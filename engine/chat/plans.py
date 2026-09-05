"""Durable Cursor-class Chat plans and two-phase Gateway execution binding."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.chat.activity import FrontendChatActivityService
from engine.chat.tables import frontend_chat_plans, frontend_conversations
from engine.contracts.frontend_chat_plan import FrontendChatPlan, PlanStep
from engine.core.command_identity import logical_command_hash
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.events.idempotency import CommandLedgerRepository
from engine.gateway.scopes import required_scope, required_target_type
from engine.truth.db import open_unit_of_work

# Deliberately excludes approvals, credential capture, candidate promotion,
# lock release/create, mission cancel and any generic raw shell operation.
PLAN_EXECUTABLE_COMMANDS: frozenset[str] = frozenset(
    {
        "frontend.chat.workspace.apply_patch",
        "frontend.chat.checkpoint.create",
        "frontend.candidate.create",
        "frontend.candidate.transition",
        "frontend.mutation.apply",
        "frontend.mutation.revert",
        "frontend.preview.start",
        "frontend.preview.set_state",
        "frontend.preview.stop",
        "frontend.verification.run",
        "frontend.coverage.recompute",
        "frontend.design.request",
        "frontend.design.try_live",
    }
)


def _plan_hash_payload(plan_id: UUID, step: PlanStep) -> str:
    encoded = json.dumps(
        {
            "plan_id": str(plan_id),
            "step_id": str(step.step_id),
            "command_type": step.command_type,
            "target_type": step.target_type,
            "target_id": str(step.target_id) if step.target_id else None,
            "parameters": step.parameters,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(encoded.encode()).hexdigest()[:24]


def _steps_dump(steps: list[PlanStep]) -> list[dict[str, object]]:
    return [step.model_dump(mode="json") for step in steps]


class FrontendChatPlanService:
    """Sole writer of conversational plan state.

    Underlying project mutations are never dispatched here. `prepare_step`
    binds the exact normal Gateway command; the client executes that separate
    command, then `record_step` proves its CommandLedger identity/result.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        activities: FrontendChatActivityService | None = None,
    ) -> None:
        self._engine = engine
        self._activities = activities or FrontendChatActivityService(engine)
        self._ledger = CommandLedgerRepository()

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        conversation_id: UUID,
        title: str,
        objective: str,
        steps: list[dict[str, object]],
        approval_required: bool,
        created_from_turn_id: UUID | None = None,
        workspace_id: UUID | None = None,
        task_graph_id: UUID | None = None,
        context_snapshot: dict[str, object] | None = None,
    ) -> FrontendChatPlan:
        if not title.strip() or not objective.strip():
            raise DdeError(
                "VALIDATION_FAILED",
                "Chat plan title and objective are required",
                retryable=False,
            )
        parsed_steps = self._parse_steps(steps, mission_id=mission_id)
        now = datetime.now(UTC)
        plan = FrontendChatPlan(
            plan_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            conversation_id=conversation_id,
            title=title.strip(),
            objective=objective.strip(),
            state="READY" if parsed_steps else "DRAFT",
            approval_required=approval_required,
            approved_by=None,
            approved_at=None,
            steps=parsed_steps,
            active_step_id=None,
            workspace_id=workspace_id,
            task_graph_id=task_graph_id,
            created_from_turn_id=created_from_turn_id,
            context_snapshot=context_snapshot,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            conversation = await uow.connection.scalar(
                select(frontend_conversations.c.conversation_id).where(
                    frontend_conversations.c.conversation_id == conversation_id,
                    frontend_conversations.c.tenant_id == tenant_id,
                    frontend_conversations.c.project_id == project_id,
                    frontend_conversations.c.mission_id == mission_id,
                    frontend_conversations.c.status == "OPEN",
                )
            )
            if conversation is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "plan target is not an open conversation in this mission",
                    retryable=False,
                )
            await uow.connection.execute(
                frontend_chat_plans.insert().values(
                    **plan.model_dump(exclude={"steps", "context_snapshot"}),
                    steps=_steps_dump(plan.steps),
                    context_snapshot=plan.context_snapshot,
                )
            )
            await uow.connection.execute(
                update(frontend_conversations)
                .where(frontend_conversations.c.conversation_id == conversation_id)
                .values(
                    active_plan_id=plan.plan_id,
                    updated_at=now,
                    lock_version=frontend_conversations.c.lock_version + 1,
                )
            )
            await uow.commit()
        await self._activities.append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            kind="PLAN_CREATED",
            state="COMPLETED",
            label=f"Plan created: {plan.title}",
            refs={"plan_id": str(plan.plan_id), "steps": len(plan.steps)},
            plan_id=plan.plan_id,
            workspace_id=workspace_id,
        )
        return plan

    def _parse_steps(
        self, raw_steps: list[dict[str, object]], *, mission_id: UUID
    ) -> list[PlanStep]:
        steps: list[PlanStep] = []
        known_ids: set[UUID] = set()
        for index, raw in enumerate(raw_steps, start=1):
            step_id = UUID(str(raw["step_id"])) if raw.get("step_id") else uuid7()
            if step_id in known_ids:
                raise DdeError(
                    "VALIDATION_FAILED", "duplicate Chat plan step id", retryable=False
                )
            known_ids.add(step_id)
            command_type = (
                str(raw["command_type"]).strip() if raw.get("command_type") else None
            )
            if command_type and command_type not in PLAN_EXECUTABLE_COMMANDS:
                raise DdeError(
                    "COMMAND_NOT_ALLOWED",
                    "command type is not admitted for automatic Chat plan execution",
                    retryable=False,
                    details={"command_type": command_type},
                )
            target_type = (
                str(raw["target_type"]).strip()
                if raw.get("target_type")
                else (required_target_type(command_type) if command_type else None)
            )
            target_id = (
                UUID(str(raw["target_id"]))
                if raw.get("target_id")
                else (mission_id if target_type == "mission" else None)
            )
            if command_type:
                self._require_executable_command(command_type, target_type)
            raw_depends = raw.get("depends_on")
            if raw_depends is None:
                depends_on: list[UUID] = []
            elif isinstance(raw_depends, list):
                depends_on = [UUID(str(item)) for item in raw_depends]
            else:
                raise DdeError(
                    "VALIDATION_FAILED",
                    "Chat plan depends_on must be a list",
                    retryable=False,
                )
            raw_parameters = raw.get("parameters")
            if raw_parameters is None:
                parameters: dict[str, object] = {}
            elif isinstance(raw_parameters, dict):
                parameters = dict(raw_parameters)
            else:
                raise DdeError(
                    "VALIDATION_FAILED",
                    "Chat plan parameters must be an object",
                    retryable=False,
                )
            steps.append(
                PlanStep(
                    step_id=step_id,
                    sequence=index,
                    title=str(raw.get("title") or f"Step {index}").strip(),
                    description=str(raw.get("description") or "").strip(),
                    state="PENDING",
                    attempt=0,
                    command_type=command_type,
                    target_type=target_type,
                    target_id=target_id,
                    parameters=parameters,
                    depends_on=depends_on,
                    evidence_refs=[],
                    command_id=None,
                    result_summary=None,
                    error_code=None,
                    error_detail=None,
                    idempotency_key=None,
                    expected_request_hash=None,
                )
            )
        ids = {step.step_id for step in steps}
        for step in steps:
            invalid = [item for item in step.depends_on if item not in ids]
            if invalid or step.step_id in step.depends_on:
                raise DdeError(
                    "VALIDATION_FAILED",
                    "Chat plan dependency references an invalid step",
                    retryable=False,
                    details={"step_id": str(step.step_id)},
                )
        self._require_acyclic(steps)
        return steps

    @staticmethod
    def _require_acyclic(steps: list[PlanStep]) -> None:
        deps = {step.step_id: set(step.depends_on) for step in steps}
        completed: set[UUID] = set()
        while len(completed) < len(steps):
            ready = [
                key
                for key, values in deps.items()
                if key not in completed and values <= completed
            ]
            if not ready:
                raise DdeError(
                    "VALIDATION_FAILED",
                    "Chat plan step dependencies contain a cycle",
                    retryable=False,
                )
            completed.update(ready)

    @staticmethod
    def _require_executable_command(command_type: str, target_type: str | None) -> None:
        if command_type not in PLAN_EXECUTABLE_COMMANDS:
            raise DdeError(
                "COMMAND_NOT_ALLOWED",
                "command type is not admitted for automatic Chat plan execution",
                retryable=False,
                details={"command_type": command_type},
            )
        scope = required_scope(command_type)
        expected_target = required_target_type(command_type)
        if scope != "mission.control" or target_type != expected_target:
            raise DdeError(
                "COMMAND_NOT_ALLOWED",
                "Chat plan command binding does not match its Gateway authority",
                retryable=False,
                details={
                    "command_type": command_type,
                    "scope": scope,
                    "target_type": target_type,
                    "expected_target_type": expected_target,
                },
            )

    async def get(
        self, *, tenant_id: UUID, project_id: UUID, plan_id: UUID
    ) -> FrontendChatPlan:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_plans).where(
                            frontend_chat_plans.c.plan_id == plan_id,
                            frontend_chat_plans.c.tenant_id == tenant_id,
                            frontend_chat_plans.c.project_id == project_id,
                        )
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            raise DdeError("POLICY_DENIED", "unknown Chat plan", retryable=False)
        return FrontendChatPlan.model_validate(dict(row))

    async def list_for_conversation(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> tuple[FrontendChatPlan, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            rows = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_plans)
                        .where(
                            frontend_chat_plans.c.conversation_id == conversation_id,
                            frontend_chat_plans.c.tenant_id == tenant_id,
                            frontend_chat_plans.c.project_id == project_id,
                        )
                        .order_by(frontend_chat_plans.c.updated_at.desc())
                    )
                )
                .mappings()
                .all()
            )
        return tuple(FrontendChatPlan.model_validate(dict(row)) for row in rows)

    async def approve(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        plan_id: UUID,
        principal_id: UUID,
        expected_lock_version: int,
    ) -> FrontendChatPlan:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                update(frontend_chat_plans)
                .where(
                    frontend_chat_plans.c.plan_id == plan_id,
                    frontend_chat_plans.c.tenant_id == tenant_id,
                    frontend_chat_plans.c.project_id == project_id,
                    frontend_chat_plans.c.lock_version == expected_lock_version,
                    frontend_chat_plans.c.state.in_(["DRAFT", "READY"]),
                )
                .values(
                    state="APPROVED",
                    approved_by=principal_id,
                    approved_at=now,
                    lock_version=frontend_chat_plans.c.lock_version + 1,
                    updated_at=now,
                )
                .returning(frontend_chat_plans)
            )
            row = result.mappings().first()
            if row is None:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Chat plan is not approvable at the supplied version",
                    retryable=False,
                )
            await uow.commit()
        return FrontendChatPlan.model_validate(dict(row))

    async def prepare_step(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        plan_id: UUID,
        step_id: UUID,
        protocol_version: str = "1",
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_plans)
                        .where(
                            frontend_chat_plans.c.plan_id == plan_id,
                            frontend_chat_plans.c.tenant_id == tenant_id,
                            frontend_chat_plans.c.project_id == project_id,
                        )
                        .with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DdeError("POLICY_DENIED", "unknown Chat plan", retryable=False)
            plan = FrontendChatPlan.model_validate(dict(row))
            if plan.state not in {"APPROVED", "EXECUTING"}:
                raise DdeError(
                    "PLAN_NOT_APPROVED",
                    "Chat plan must be approved before execution",
                    retryable=False,
                    details={"state": plan.state},
                )
            steps = list(plan.steps)
            index = next(
                (i for i, item in enumerate(steps) if item.step_id == step_id), None
            )
            if index is None:
                raise DdeError(
                    "POLICY_DENIED", "unknown Chat plan step", retryable=False
                )
            step = steps[index]
            if step.state == "COMPLETED":
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Chat plan step is already complete",
                    retryable=False,
                )
            dependencies = {item.step_id: item.state for item in steps}
            blocked = [
                str(dep)
                for dep in step.depends_on
                if dependencies.get(dep) != "COMPLETED"
            ]
            if blocked:
                raise DdeError(
                    "PLAN_DEPENDENCY_BLOCKED",
                    "Chat plan step dependencies are not complete",
                    retryable=False,
                    details={"dependency_ids": blocked},
                )
            if not step.command_type or not step.target_type or not step.target_id:
                raise DdeError(
                    "COMMAND_NOT_ALLOWED",
                    "Chat plan step has no executable command binding",
                    retryable=False,
                )
            self._require_executable_command(step.command_type, step.target_type)
            if step.target_type == "mission" and step.target_id != plan.mission_id:
                raise DdeError(
                    "TENANT_SCOPE_VIOLATION",
                    "Chat plan step may address only its mission",
                    retryable=False,
                )
            step_digest = _plan_hash_payload(plan.plan_id, step)
            next_attempt = step.attempt + 1
            idempotency_key = (
                f"chat-plan:{plan.plan_id}:{step.step_id}:{step_digest}:a{next_attempt}"
            )
            expected_hash = logical_command_hash(
                command_type=step.command_type,
                target_type=step.target_type,
                target_id=step.target_id,
                parameters=step.parameters,
                protocol_version=protocol_version,
            )
            steps[index] = step.model_copy(
                update={
                    "state": "READY",
                    "attempt": next_attempt,
                    "idempotency_key": idempotency_key,
                    "expected_request_hash": expected_hash,
                    "error_code": None,
                    "error_detail": None,
                }
            )
            await uow.connection.execute(
                update(frontend_chat_plans)
                .where(frontend_chat_plans.c.plan_id == plan_id)
                .values(
                    state="EXECUTING",
                    active_step_id=step_id,
                    steps=_steps_dump(steps),
                    lock_version=frontend_chat_plans.c.lock_version + 1,
                    updated_at=now,
                )
            )
            await uow.commit()
        await self._activities.append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=plan.conversation_id,
            kind="TOOL_PROPOSED",
            state="COMPLETED",
            label=f"Prepared plan step {step.sequence}: {step.title}",
            refs={
                "plan_id": str(plan_id),
                "step_id": str(step_id),
                "command_type": step.command_type,
                "request_hash": expected_hash,
            },
            plan_id=plan_id,
            workspace_id=plan.workspace_id,
        )
        return {
            "plan_id": str(plan_id),
            "step_id": str(step_id),
            "command_type": step.command_type,
            "target_type": step.target_type,
            "target_id": str(step.target_id),
            "parameters": step.parameters,
            "idempotency_key": idempotency_key,
            "protocol_version": protocol_version,
            "expected_request_hash": expected_hash,
        }

    async def record_step(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        plan_id: UUID,
        step_id: UUID,
        command_id: UUID,
    ) -> FrontendChatPlan:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_plans)
                        .where(
                            frontend_chat_plans.c.plan_id == plan_id,
                            frontend_chat_plans.c.tenant_id == tenant_id,
                            frontend_chat_plans.c.project_id == project_id,
                        )
                        .with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DdeError("POLICY_DENIED", "unknown Chat plan", retryable=False)
            plan = FrontendChatPlan.model_validate(dict(row))
            steps = list(plan.steps)
            index = next(
                (i for i, item in enumerate(steps) if item.step_id == step_id), None
            )
            if index is None:
                raise DdeError(
                    "POLICY_DENIED", "unknown Chat plan step", retryable=False
                )
            step = steps[index]
            if not step.idempotency_key or not step.expected_request_hash:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Chat plan step was not prepared before result recording",
                    retryable=False,
                )
            ledger = await self._ledger.get_by_id(uow.connection, command_id)
            if (
                ledger is None
                or ledger.tenant_id != tenant_id
                or ledger.project_id != project_id
            ):
                raise DdeError(
                    "CONTEXT_INCOMPLETE",
                    "Gateway command result is not visible in this project",
                    retryable=True,
                )
            if (
                ledger.idempotency_key != step.idempotency_key
                or ledger.request_hash != step.expected_request_hash
            ):
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Gateway command does not match the exact prepared Chat plan step",
                    retryable=False,
                    details={"command_id": str(command_id)},
                )
            if ledger.status == "completed":
                state = "COMPLETED"
                error_code = None
                error_detail = None
            elif ledger.status == "failed":
                state = "FAILED"
                error_code = "COMMAND_FAILED"
                error_detail = json.dumps(
                    ledger.result or {}, sort_keys=True, default=str
                )
            else:
                state = "SUBMITTED"
                error_code = None
                error_detail = None
            steps[index] = step.model_copy(
                update={
                    "state": state,
                    "command_id": command_id,
                    "result_summary": json.dumps(
                        ledger.result or {}, sort_keys=True, default=str
                    )[:4000],
                    "error_code": error_code,
                    "error_detail": error_detail,
                }
            )
            terminal = all(item.state in {"COMPLETED", "SKIPPED"} for item in steps)
            any_failed = any(item.state == "FAILED" for item in steps)
            next_state = (
                "COMPLETED" if terminal else ("FAILED" if any_failed else "EXECUTING")
            )
            active_step = None if terminal or any_failed else step_id
            result = await uow.connection.execute(
                update(frontend_chat_plans)
                .where(frontend_chat_plans.c.plan_id == plan_id)
                .values(
                    steps=_steps_dump(steps),
                    state=next_state,
                    active_step_id=active_step,
                    lock_version=frontend_chat_plans.c.lock_version + 1,
                    updated_at=now,
                )
                .returning(frontend_chat_plans)
            )
            updated = result.mappings().one()
            await uow.commit()
        await self._activities.append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=plan.conversation_id,
            kind="COMMAND_ACCEPTED" if state != "FAILED" else "COMMAND_FAILED",
            state="COMPLETED"
            if state == "COMPLETED"
            else ("FAILED" if state == "FAILED" else "RUNNING"),
            label=f"Plan step {step.sequence}: {step.title}",
            detail=f"Gateway command {command_id} is {ledger.status}",
            refs={"plan_id": str(plan_id), "step_id": str(step_id)},
            plan_id=plan_id,
            workspace_id=plan.workspace_id,
            command_id=command_id,
        )
        return FrontendChatPlan.model_validate(dict(updated))

    async def update(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        plan_id: UUID,
        expected_lock_version: int,
        title: str | None = None,
        objective: str | None = None,
        steps: list[dict[str, object]] | None = None,
    ) -> FrontendChatPlan:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_plans)
                        .where(
                            frontend_chat_plans.c.plan_id == plan_id,
                            frontend_chat_plans.c.tenant_id == tenant_id,
                            frontend_chat_plans.c.project_id == project_id,
                            frontend_chat_plans.c.lock_version == expected_lock_version,
                        )
                        .with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DdeError("VERSION_CONFLICT", "stale or unknown Chat plan")
            plan = FrontendChatPlan.model_validate(dict(row))
            if plan.state not in {"DRAFT", "READY"}:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "approved/executing Chat plan cannot be edited in place",
                    retryable=False,
                )
            next_steps = (
                self._parse_steps(steps, mission_id=plan.mission_id)
                if steps is not None
                else list(plan.steps)
            )
            next_title = title.strip() if title is not None else plan.title
            next_objective = (
                objective.strip() if objective is not None else plan.objective
            )
            if not next_title or not next_objective:
                raise DdeError(
                    "VALIDATION_FAILED",
                    "Chat plan title and objective are required",
                    retryable=False,
                )
            result = await uow.connection.execute(
                update(frontend_chat_plans)
                .where(frontend_chat_plans.c.plan_id == plan_id)
                .values(
                    title=next_title,
                    objective=next_objective,
                    steps=_steps_dump(next_steps),
                    state="READY" if next_steps else "DRAFT",
                    approved_by=None,
                    approved_at=None,
                    active_step_id=None,
                    lock_version=frontend_chat_plans.c.lock_version + 1,
                    updated_at=now,
                )
                .returning(frontend_chat_plans)
            )
            updated = result.mappings().one()
            await uow.commit()
        return FrontendChatPlan.model_validate(dict(updated))

    async def retry_step(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        plan_id: UUID,
        step_id: UUID,
    ) -> FrontendChatPlan:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_plans)
                        .where(
                            frontend_chat_plans.c.plan_id == plan_id,
                            frontend_chat_plans.c.tenant_id == tenant_id,
                            frontend_chat_plans.c.project_id == project_id,
                        )
                        .with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DdeError("POLICY_DENIED", "unknown Chat plan", retryable=False)
            plan = FrontendChatPlan.model_validate(dict(row))
            steps = list(plan.steps)
            index = next(
                (i for i, item in enumerate(steps) if item.step_id == step_id), None
            )
            if index is None:
                raise DdeError(
                    "POLICY_DENIED", "unknown Chat plan step", retryable=False
                )
            step = steps[index]
            if step.state not in {"FAILED", "BLOCKED", "CANCELLED"}:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "only failed, blocked or cancelled plan steps may retry",
                    retryable=False,
                )
            steps[index] = step.model_copy(
                update={
                    "state": "PENDING",
                    "command_id": None,
                    "idempotency_key": None,
                    "expected_request_hash": None,
                    "result_summary": None,
                    "error_code": None,
                    "error_detail": None,
                }
            )
            result = await uow.connection.execute(
                update(frontend_chat_plans)
                .where(frontend_chat_plans.c.plan_id == plan_id)
                .values(
                    state="APPROVED" if plan.approved_at else "READY",
                    active_step_id=None,
                    steps=_steps_dump(steps),
                    lock_version=frontend_chat_plans.c.lock_version + 1,
                    updated_at=now,
                )
                .returning(frontend_chat_plans)
            )
            updated = result.mappings().one()
            await uow.commit()
        return FrontendChatPlan.model_validate(dict(updated))

    async def cancel(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        plan_id: UUID,
        expected_lock_version: int,
    ) -> FrontendChatPlan:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_chat_plans)
                        .where(
                            frontend_chat_plans.c.plan_id == plan_id,
                            frontend_chat_plans.c.tenant_id == tenant_id,
                            frontend_chat_plans.c.project_id == project_id,
                            frontend_chat_plans.c.lock_version == expected_lock_version,
                        )
                        .with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DdeError(
                    "VERSION_CONFLICT", "stale or unknown Chat plan", retryable=False
                )
            plan = FrontendChatPlan.model_validate(dict(row))
            if plan.state in {"COMPLETED", "FAILED", "CANCELLED"}:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "terminal Chat plan cannot be cancelled",
                    retryable=False,
                )
            steps = [
                item.model_copy(update={"state": "CANCELLED"})
                if item.state in {"PENDING", "READY"}
                else item
                for item in plan.steps
            ]
            result = await uow.connection.execute(
                update(frontend_chat_plans)
                .where(frontend_chat_plans.c.plan_id == plan_id)
                .values(
                    state="CANCELLED",
                    active_step_id=None,
                    steps=_steps_dump(steps),
                    lock_version=frontend_chat_plans.c.lock_version + 1,
                    updated_at=now,
                )
                .returning(frontend_chat_plans)
            )
            updated = result.mappings().one()
            await uow.commit()
        return FrontendChatPlan.model_validate(dict(updated))
