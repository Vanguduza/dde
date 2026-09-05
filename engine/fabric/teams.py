"""Bounded multi-agent team topology and delegation authority."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.ai_agent_team import AgentMember, AiAgentTeam
from engine.core.errors import BudgetExhaustedError, DdeError
from engine.core.ids import uuid7
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import ai_agent_teams

_MEMBER_TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING": frozenset({"RUNNING", "CANCELLED", "BLOCKED"}),
    "RUNNING": frozenset({"PAUSED", "COMPLETED", "FAILED", "CANCELLED", "BLOCKED"}),
    "PAUSED": frozenset({"RUNNING", "CANCELLED", "BLOCKED"}),
    "BLOCKED": frozenset({"RUNNING", "CANCELLED"}),
    "FAILED": frozenset(),
    "COMPLETED": frozenset(),
    "CANCELLED": frozenset(),
}
_TEAM_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"RUNNING", "CANCELLED"}),
    "RUNNING": frozenset({"PAUSED", "COMPLETED", "FAILED", "CANCELLED"}),
    "PAUSED": frozenset({"RUNNING", "CANCELLED", "FAILED"}),
    "COMPLETED": frozenset(),
    "FAILED": frozenset(),
    "CANCELLED": frozenset(),
}


def _number(value: object | None) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def validate_child_budget(parent: dict[str, object], child: dict[str, object]) -> None:
    for key in ("cost_usd", "tokens", "turns"):
        parent_value = _number(parent.get(key))
        child_value = _number(child.get(key))
        if child_value is not None and child_value < 0:
            raise DdeError(
                "VALIDATION_FAILED", f"child {key} budget cannot be negative"
            )
        if (
            parent_value is not None
            and child_value is not None
            and child_value > parent_value
        ):
            raise BudgetExhaustedError(
                "child agent budget exceeds parent/team ceiling",
                details={
                    "budget_key": key,
                    "parent": parent_value,
                    "child": child_value,
                },
            )


class AgentTeamService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.repo = FabricRepository(engine)

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        strategy: str,
        max_depth: int = 2,
        max_children: int = 3,
        aggregate_budget: dict[str, object] | None = None,
        mission_id: UUID | None = None,
        manager_profile_id: str | None = None,
    ) -> AiAgentTeam:
        if not 1 <= max_depth <= 8 or not 1 <= max_children <= 32:
            raise DdeError(
                "VALIDATION_FAILED",
                "agent team depth/child limit is outside safe bounds",
            )
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "team_id": uuid7(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "conversation_id": conversation_id,
            "mission_id": mission_id,
            "strategy": strategy,
            "state": "DRAFT",
            "manager_profile_id": manager_profile_id,
            "max_depth": max_depth,
            "max_children": max_children,
            "aggregate_budget": aggregate_budget or {},
            "members": [],
            "result_refs": [],
            "lock_version": 1,
            "created_at": now,
            "updated_at": now,
        }
        AiAgentTeam.model_validate(values)
        return await self.repo.insert_model(
            table=ai_agent_teams,
            model=AiAgentTeam,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )

    async def add_member(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        team_id: UUID,
        role: str,
        toolset_ids: list[str],
        budget: dict[str, object] | None,
        lock_version: int,
        parent_member_id: UUID | None = None,
        task_id: UUID | None = None,
        worker_session_id: UUID | None = None,
        workspace_id: UUID | None = None,
        model_profile_id: str | None = None,
        allowed_toolset_ids: list[str] | None = None,
    ) -> AiAgentTeam:
        team = await self.get(
            tenant_id=tenant_id, project_id=project_id, team_id=team_id
        )
        if team.state not in {"DRAFT", "RUNNING", "PAUSED"}:
            raise DdeError("VERSION_CONFLICT", "terminal team cannot accept members")
        if len(team.members) >= team.max_children * max(team.max_depth, 1):
            raise DdeError("RESOURCE_EXHAUSTION", "team member bound reached")
        parent = next(
            (m for m in team.members if m.member_id == parent_member_id), None
        )
        if parent_member_id is not None and parent is None:
            raise DdeError("CONTEXT_INCOMPLETE", "parent team member not found")
        depth = 0 if parent is None else parent.depth + 1
        if depth > team.max_depth:
            raise DdeError(
                "POLICY_DENIED", "subagent delegation depth exceeds team limit"
            )
        siblings = [m for m in team.members if m.parent_member_id == parent_member_id]
        if len(siblings) >= team.max_children:
            raise DdeError("POLICY_DENIED", "subagent child limit exceeded")
        allowed = set(allowed_toolset_ids or toolset_ids)
        if not set(toolset_ids) <= allowed:
            raise DdeError(
                "POLICY_DENIED",
                "child agent toolset would widen delegated authority",
                details={
                    "requested": sorted(set(toolset_ids)),
                    "allowed": sorted(allowed),
                },
            )
        parent_budget = (
            parent.budget
            if parent and parent.budget is not None
            else team.aggregate_budget
        )
        validate_child_budget(parent_budget, budget or {})
        member = AgentMember(
            member_id=uuid7(),
            parent_member_id=parent_member_id,
            role=role.strip(),
            task_id=task_id,
            worker_session_id=worker_session_id,
            workspace_id=workspace_id,
            model_profile_id=model_profile_id,
            state="PENDING",
            depth=depth,
            toolset_ids=sorted(set(toolset_ids)),
            budget=budget or {},
            result_refs=[],
            error_detail=None,
        )
        return await self.repo.update_locked(
            table=ai_agent_teams,
            model=AiAgentTeam,
            id_column="team_id",
            object_id=team_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={
                "members": [
                    *(m.model_dump() for m in team.members),
                    member.model_dump(),
                ],
                "updated_at": datetime.now(UTC),
            },
        )

    async def transition_member(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        team_id: UUID,
        member_id: UUID,
        target: str,
        lock_version: int,
        result_refs: list[str] | None = None,
        error_detail: str | None = None,
    ) -> AiAgentTeam:
        team = await self.get(
            tenant_id=tenant_id, project_id=project_id, team_id=team_id
        )
        members = list(team.members)
        index = next(
            (i for i, m in enumerate(members) if m.member_id == member_id), None
        )
        if index is None:
            raise DdeError("CONTEXT_INCOMPLETE", "team member not found")
        member = members[index]
        if target not in _MEMBER_TRANSITIONS[member.state]:
            raise DdeError(
                "VERSION_CONFLICT",
                "illegal agent member transition",
                details={"from": member.state, "to": target},
            )
        members[index] = member.model_copy(
            update={
                "state": target,
                "result_refs": result_refs
                if result_refs is not None
                else member.result_refs,
                "error_detail": error_detail,
            }
        )
        return await self.repo.update_locked(
            table=ai_agent_teams,
            model=AiAgentTeam,
            id_column="team_id",
            object_id=team_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={
                "members": [m.model_dump() for m in members],
                "updated_at": datetime.now(UTC),
            },
        )

    async def transition_team(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        team_id: UUID,
        target: str,
        lock_version: int,
        result_refs: list[str] | None = None,
    ) -> AiAgentTeam:
        team = await self.get(
            tenant_id=tenant_id, project_id=project_id, team_id=team_id
        )
        if target not in _TEAM_TRANSITIONS[team.state]:
            raise DdeError("VERSION_CONFLICT", "illegal agent team transition")
        if target == "COMPLETED" and any(
            m.state not in {"COMPLETED", "CANCELLED"} for m in team.members
        ):
            raise DdeError(
                "VERSION_CONFLICT", "team cannot complete while members are nonterminal"
            )
        return await self.repo.update_locked(
            table=ai_agent_teams,
            model=AiAgentTeam,
            id_column="team_id",
            object_id=team_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={
                "state": target,
                "result_refs": result_refs
                if result_refs is not None
                else team.result_refs,
                "updated_at": datetime.now(UTC),
            },
        )

    async def get(
        self, *, tenant_id: UUID, project_id: UUID, team_id: UUID
    ) -> AiAgentTeam:
        return await self.repo.get_model(
            table=ai_agent_teams,
            model=AiAgentTeam,
            id_column="team_id",
            object_id=team_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )

    async def list_for_conversation(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> tuple[AiAgentTeam, ...]:
        return await self.repo.list_models(
            table=ai_agent_teams,
            model=AiAgentTeam,
            tenant_id=tenant_id,
            project_id=project_id,
            filters={"conversation_id": conversation_id},
            order_by=(ai_agent_teams.c.updated_at.desc(),),
        )
