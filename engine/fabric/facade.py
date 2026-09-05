"""Gateway-facing command façade for the AI Conversation Fabric.

The façade maps already-authorized commands onto bounded Fabric services. It
contains no provider bypass and no alternate mutation path.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, overload
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.core.errors import DdeError
from engine.fabric.automations import AutomationService
from engine.fabric.bindings import ConversationFabricBindingService
from engine.fabric.claims import ClaimService
from engine.fabric.context import ContextSnapshotService
from engine.fabric.experience import ExperienceService
from engine.fabric.hooks import HookService
from engine.fabric.interop import AgentInteropService
from engine.fabric.memory import MemoryService
from engine.fabric.policies import ConversationPolicyService
from engine.fabric.research import ResearchService
from engine.fabric.runtime import AgentInteropRuntimeService
from engine.fabric.sessions import WorkerSessionService
from engine.fabric.skills import SkillService
from engine.fabric.teams import AgentTeamService


@overload
def _uuid(
    p: dict[str, object], key: str, *, optional: Literal[False] = False
) -> UUID: ...


@overload
def _uuid(
    p: dict[str, object], key: str, *, optional: Literal[True]
) -> UUID | None: ...


def _uuid(p: dict[str, object], key: str, *, optional: bool = False) -> UUID | None:
    value = p.get(key)
    if value is None and optional:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise DdeError("VALIDATION_FAILED", f"{key} must be a UUID") from exc


def _str(p: dict[str, object], key: str, *, optional: bool = False) -> str | None:
    value = p.get(key)
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise DdeError("VALIDATION_FAILED", f"{key} must be non-empty text")
    return value.strip()


def _int(p: dict[str, object], key: str, default: int | None = None) -> int:
    value = p.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise DdeError("VALIDATION_FAILED", f"{key} must be an integer")
    return value


def _float(p: dict[str, object], key: str, default: float | None = None) -> float:
    value = p.get(key, default)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise DdeError("VALIDATION_FAILED", f"{key} must be numeric")
    return float(value)


def _optional_float(p: dict[str, object], key: str) -> float | None:
    if p.get(key) is None:
        return None
    return _float(p, key)


def _optional_int(p: dict[str, object], key: str) -> int | None:
    if p.get(key) is None:
        return None
    return _int(p, key)


def _bool(p: dict[str, object], key: str, default: bool = False) -> bool:
    value = p.get(key, default)
    if not isinstance(value, bool):
        raise DdeError("VALIDATION_FAILED", f"{key} must be boolean")
    return value


def _list(p: dict[str, object], key: str) -> list[object]:
    value = p.get(key, [])
    if not isinstance(value, list):
        raise DdeError("VALIDATION_FAILED", f"{key} must be a list")
    return value


def _strs(p: dict[str, object], key: str) -> list[str]:
    values = _list(p, key)
    if not all(isinstance(v, str) for v in values):
        raise DdeError("VALIDATION_FAILED", f"{key} must contain only strings")
    return [str(v) for v in values]


def _dict(p: dict[str, object], key: str) -> dict[str, object]:
    value = p.get(key, {})
    if not isinstance(value, dict):
        raise DdeError("VALIDATION_FAILED", f"{key} must be an object")
    return {str(k): v for k, v in value.items()}


def _datetime(p: dict[str, object], key: str) -> datetime | None:
    value = p.get(key)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise DdeError("VALIDATION_FAILED", f"{key} must be ISO datetime") from exc
    raise DdeError("VALIDATION_FAILED", f"{key} must be ISO datetime")


def _dump(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [_dump(item) for item in value]
    return value


class AiConversationFabricFacade:
    def __init__(self, engine: AsyncEngine) -> None:
        self.policies = ConversationPolicyService(engine)
        self.bindings = ConversationFabricBindingService(engine)
        self.interop = AgentInteropService(engine)
        self.sessions = WorkerSessionService(engine)
        self.runtime = AgentInteropRuntimeService(engine)
        self.memory = MemoryService(engine)
        self.context = ContextSnapshotService(engine)
        self.skills = SkillService(engine)
        self.teams = AgentTeamService(engine)
        self.research = ResearchService(engine)
        self.automations = AutomationService(engine)
        self.hooks = HookService(engine)
        self.claims = ClaimService(engine)
        self.experience = ExperienceService(engine)

    async def execute(
        self,
        *,
        command_type: str,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID,
        principal_id: UUID,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        if command_type.startswith("dde.fabric."):
            command_type = command_type.replace("dde.fabric.", "frontend.fabric.", 1)
        p = parameters
        item: object
        if command_type == "frontend.fabric.policy.create":
            item = await self.policies.create(
                tenant_id=tenant_id,
                project_id=project_id,
                name=str(_str(p, "name")),
                reasoning_effort=str(p.get("reasoning_effort", "NORMAL")),
                permission_profile=str(p.get("permission_profile", "APPROVAL_GATED")),
                toolset_ids=_strs(p, "toolset_ids"),
                allowed_capability_ids=_strs(p, "allowed_capability_ids"),
                denied_capability_ids=_strs(p, "denied_capability_ids"),
                fallback_chain=[
                    dict(v) for v in _list(p, "fallback_chain") if isinstance(v, dict)
                ],
                max_turns=_optional_int(p, "max_turns"),
                context_token_budget=_int(p, "context_token_budget", 24000),
                cost_budget_usd=_optional_float(p, "cost_budget_usd"),
                quality_priority=_int(p, "quality_priority", 90),
                latency_priority=_int(p, "latency_priority", 40),
                independent_review_required=_bool(p, "independent_review_required"),
                created_by=principal_id,
            )
        elif command_type == "frontend.fabric.policy.bind":
            item = await self.bindings.bind_policy(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                policy_id=_uuid(p, "policy_id", optional=True),
                lock_version=_int(p, "lock_version"),
            )
        elif command_type == "frontend.fabric.interop.discover":
            item = await self.interop.discover_local(
                tenant_id=tenant_id, project_id=project_id
            )
        elif command_type == "frontend.fabric.interop.register":
            item = await self.interop.register_external(
                tenant_id=tenant_id,
                project_id=project_id,
                harness_id=str(_str(p, "harness_id")),
                protocol=str(_str(p, "protocol")),
                executable_or_uri=str(_str(p, "executable_or_uri")),
                discovered_capabilities=_dict(p, "discovered_capabilities"),
            )
        elif command_type == "frontend.fabric.interop.certify":
            item = await self.interop.certify(
                tenant_id=tenant_id,
                project_id=project_id,
                endpoint_id=_uuid(p, "endpoint_id"),
                certified_capabilities=_dict(p, "certified_capabilities"),
                certification_refs=_strs(p, "certification_refs"),
                lock_version=_int(p, "lock_version"),
            )
        elif command_type == "frontend.fabric.capacity.record":
            optional = {
                k: p[k]
                for k in (
                    "reset_at",
                    "reset_source",
                    "active_concurrency",
                    "max_concurrency",
                    "latency_ms",
                    "recent_failures",
                    "input_cost_per_million",
                    "output_cost_per_million",
                )
                if k in p
            }
            if isinstance(optional.get("reset_at"), str):
                optional["reset_at"] = _datetime(p, "reset_at")
            item = await self.interop.record_capacity(
                tenant_id=tenant_id,
                project_id=project_id,
                endpoint_id=_uuid(p, "endpoint_id"),
                provider_id=str(_str(p, "provider_id")),
                state=str(_str(p, "state")),
                confidence=_float(p, "confidence", 0.0),
                quota_metadata=_dict(p, "quota_metadata"),
                **optional,
            )
        elif command_type == "frontend.fabric.session.open":
            item = await self.sessions.open(
                tenant_id=tenant_id,
                project_id=project_id,
                endpoint_id=_uuid(p, "endpoint_id"),
                mission_id=mission_id,
                worker_profile_id=_str(p, "worker_profile_id", optional=True),
                requested_model_id=_str(p, "requested_model_id", optional=True),
                workspace_id=_uuid(p, "workspace_id", optional=True),
                context_package_hash=_str(p, "context_package_hash", optional=True),
                tool_policy_hash=_str(p, "tool_policy_hash", optional=True),
                session_config=_dict(p, "session_config"),
            )
        elif command_type == "frontend.fabric.session.bind":
            item = await self.bindings.bind_session(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                worker_session_id=_uuid(p, "worker_session_id", optional=True),
                lock_version=_int(p, "lock_version"),
            )
        elif command_type == "frontend.fabric.session.fork":
            item = await self.sessions.fork(
                tenant_id=tenant_id,
                project_id=project_id,
                worker_session_id=_uuid(p, "worker_session_id"),
                session_config=_dict(p, "session_config"),
            )
        elif command_type == "frontend.fabric.session.transition":
            item = await self.sessions.transition(
                tenant_id=tenant_id,
                project_id=project_id,
                worker_session_id=_uuid(p, "worker_session_id"),
                lock_version=_int(p, "lock_version"),
                target=str(_str(p, "target")),
                detail=_str(p, "detail", optional=True),
            )
        elif command_type == "frontend.fabric.provider.invoke":
            result = await self.runtime.invoke_conversation(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                prompt=str(_str(p, "prompt")),
                context=_dict(p, "context"),
                approval_id=_uuid(p, "approval_id", optional=True),
                endpoint_id=_uuid(p, "endpoint_id", optional=True),
            )
            return {
                "result": {
                    "text": result.text,
                    "reasoning": result.reasoning,
                    "invocation": _dump(result.invocation),
                    "session": _dump(result.session),
                    "updates": list(result.updates),
                },
                "side_effect_class": "PROVIDER_EXTERNAL",
            }
        elif command_type == "frontend.fabric.memory.propose":
            item = await self.memory.propose(
                tenant_id=tenant_id,
                project_id=project_id,
                scope_kind=str(_str(p, "scope_kind")),
                scope_ref=str(_str(p, "scope_ref")),
                content=str(_str(p, "content")),
                source_type=str(_str(p, "source_type")),
                source_refs=_strs(p, "source_refs"),
                trust_class=str(p.get("trust_class", "ADVISORY")),
                proposed_by_profile_id=_str(p, "proposed_by_profile_id", optional=True),
                metadata=_dict(p, "metadata"),
                fresh_until=_datetime(p, "fresh_until"),
            )
        elif command_type == "frontend.fabric.memory.approve":
            item = await self.memory.approve(
                tenant_id=tenant_id,
                project_id=project_id,
                memory_id=_uuid(p, "memory_id"),
                principal_id=principal_id,
                lock_version=_int(p, "lock_version"),
            )
        elif command_type == "frontend.fabric.memory.reject":
            item = await self.memory.reject(
                tenant_id=tenant_id,
                project_id=project_id,
                memory_id=_uuid(p, "memory_id"),
                lock_version=_int(p, "lock_version"),
            )
        elif command_type == "frontend.fabric.memory.supersede":
            item = await self.memory.supersede(
                tenant_id=tenant_id,
                project_id=project_id,
                memory_id=_uuid(p, "memory_id"),
                replacement_content=str(_str(p, "replacement_content")),
                source_refs=_strs(p, "source_refs"),
                principal_id=principal_id,
            )
        elif command_type == "frontend.fabric.context.snapshot":
            item = await self.context.create(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                reason=str(_str(p, "reason")),
                retained_refs=_strs(p, "retained_refs"),
                omitted_refs=_strs(p, "omitted_refs"),
                omission_reasons={
                    str(k): str(v) for k, v in _dict(p, "omission_reasons").items()
                },
                item_manifest=[
                    dict(v) for v in _list(p, "item_manifest") if isinstance(v, dict)
                ],
                estimated_tokens=_int(p, "estimated_tokens"),
                budget_tokens=_int(p, "budget_tokens"),
                summary=_str(p, "summary", optional=True),
                turn_id=_uuid(p, "turn_id", optional=True),
                predecessor_snapshot_id=_uuid(
                    p, "predecessor_snapshot_id", optional=True
                ),
            )
        elif command_type == "frontend.fabric.skill.propose":
            item = await self.skills.propose(
                tenant_id=tenant_id,
                project_id=project_id,
                slug=str(_str(p, "slug")),
                version=str(_str(p, "version")),
                title=str(_str(p, "title")),
                description=str(_str(p, "description")),
                instructions=str(_str(p, "instructions")),
                source_kind=str(_str(p, "source_kind")),
                source_ref=_str(p, "source_ref", optional=True),
                provenance_refs=_strs(p, "provenance_refs"),
                license=_str(p, "license", optional=True),
                required_capability_ids=_strs(p, "required_capability_ids"),
                toolset_ids=_strs(p, "toolset_ids"),
                parent_skill_id=_uuid(p, "parent_skill_id", optional=True),
            )
        elif command_type == "frontend.fabric.skill.begin_evaluation":
            item = await self.skills.begin_evaluation(
                tenant_id=tenant_id,
                project_id=project_id,
                skill_id=_uuid(p, "skill_id"),
                lock_version=_int(p, "lock_version"),
            )
        elif command_type == "frontend.fabric.skill.certify":
            item = await self.skills.certify(
                tenant_id=tenant_id,
                project_id=project_id,
                skill_id=_uuid(p, "skill_id"),
                principal_id=principal_id,
                evaluation_refs=_strs(p, "evaluation_refs"),
                lock_version=_int(p, "lock_version"),
            )
        elif command_type == "frontend.fabric.skill.reject":
            item = await self.skills.reject(
                tenant_id=tenant_id,
                project_id=project_id,
                skill_id=_uuid(p, "skill_id"),
                evaluation_refs=_strs(p, "evaluation_refs"),
                lock_version=_int(p, "lock_version"),
            )
        elif command_type == "frontend.fabric.team.create":
            item = await self.teams.create(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                strategy=str(_str(p, "strategy")),
                max_depth=_int(p, "max_depth", 2),
                max_children=_int(p, "max_children", 3),
                aggregate_budget=_dict(p, "aggregate_budget"),
                mission_id=mission_id,
                manager_profile_id=_str(p, "manager_profile_id", optional=True),
            )
        elif command_type == "frontend.fabric.team.add_member":
            item = await self.teams.add_member(
                tenant_id=tenant_id,
                project_id=project_id,
                team_id=_uuid(p, "team_id"),
                role=str(_str(p, "role")),
                toolset_ids=_strs(p, "toolset_ids"),
                budget=_dict(p, "budget"),
                lock_version=_int(p, "lock_version"),
                parent_member_id=_uuid(p, "parent_member_id", optional=True),
                task_id=_uuid(p, "task_id", optional=True),
                worker_session_id=_uuid(p, "worker_session_id", optional=True),
                workspace_id=_uuid(p, "workspace_id", optional=True),
                model_profile_id=_str(p, "model_profile_id", optional=True),
                allowed_toolset_ids=_strs(p, "allowed_toolset_ids"),
            )
        elif command_type == "frontend.fabric.team.transition_member":
            item = await self.teams.transition_member(
                tenant_id=tenant_id,
                project_id=project_id,
                team_id=_uuid(p, "team_id"),
                member_id=_uuid(p, "member_id"),
                target=str(_str(p, "target")),
                lock_version=_int(p, "lock_version"),
                result_refs=_strs(p, "result_refs"),
                error_detail=_str(p, "error_detail", optional=True),
            )
        elif command_type == "frontend.fabric.team.transition":
            item = await self.teams.transition_team(
                tenant_id=tenant_id,
                project_id=project_id,
                team_id=_uuid(p, "team_id"),
                target=str(_str(p, "target")),
                lock_version=_int(p, "lock_version"),
                result_refs=_strs(p, "result_refs"),
            )
        elif command_type == "frontend.fabric.research.create":
            item = await self.research.create(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                mode=str(_str(p, "mode")),
                question=str(_str(p, "question")),
                scope=_dict(p, "scope"),
                mission_id=mission_id,
                created_from_turn_id=_uuid(p, "created_from_turn_id", optional=True),
            )
        elif command_type == "frontend.fabric.research.add_source":
            item = await self.research.add_source(
                tenant_id=tenant_id,
                project_id=project_id,
                research_id=_uuid(p, "research_id"),
                source_kind=str(_str(p, "source_kind")),
                ref=str(_str(p, "ref")),
                authority=str(_str(p, "authority")),
                lock_version=_int(p, "lock_version"),
                title=_str(p, "title", optional=True),
                published_at=_datetime(p, "published_at"),
                content_hash=_str(p, "content_hash", optional=True),
                notes=_str(p, "notes", optional=True),
            )
        elif command_type == "frontend.fabric.research.update":
            item = await self.research.update_analysis(
                tenant_id=tenant_id,
                project_id=project_id,
                research_id=_uuid(p, "research_id"),
                lock_version=_int(p, "lock_version"),
                findings=[dict(v) for v in _list(p, "findings") if isinstance(v, dict)],
                hypotheses=[
                    dict(v) for v in _list(p, "hypotheses") if isinstance(v, dict)
                ],
                unresolved_questions=_strs(p, "unresolved_questions"),
                result_refs=_strs(p, "result_refs"),
            )
        elif command_type == "frontend.fabric.research.complete":
            item = await self.research.complete(
                tenant_id=tenant_id,
                project_id=project_id,
                research_id=_uuid(p, "research_id"),
                lock_version=_int(p, "lock_version"),
                confidence=_float(p, "confidence", 0.0),
                result_refs=_strs(p, "result_refs"),
            )
        elif command_type == "frontend.fabric.research.to_plan":
            item = await self.research.to_plan(
                tenant_id=tenant_id,
                project_id=project_id,
                research_id=_uuid(p, "research_id"),
                mission_id=mission_id,
                selected_finding_indexes=[
                    int(v)
                    for v in _list(p, "selected_finding_indexes")
                    if isinstance(v, int)
                ],
                title=str(_str(p, "title")),
            )
        elif command_type == "frontend.fabric.automation.create":
            item = await self.automations.create(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                name=str(_str(p, "name")),
                schedule_kind=str(_str(p, "schedule_kind")),
                schedule_expression=str(_str(p, "schedule_expression")),
                timezone=str(_str(p, "timezone")),
                action_kind=str(_str(p, "action_kind")),
                action_payload=_dict(p, "action_payload"),
                mission_id=mission_id,
                created_by=principal_id,
            )
        elif command_type == "frontend.fabric.automation.set_state":
            item = await self.automations.set_state(
                tenant_id=tenant_id,
                project_id=project_id,
                automation_id=_uuid(p, "automation_id"),
                lock_version=_int(p, "lock_version"),
                state=str(_str(p, "state")),
            )
        elif command_type == "frontend.fabric.automation.record_result":
            item = await self.automations.record_result(
                tenant_id=tenant_id,
                project_id=project_id,
                automation_id=_uuid(p, "automation_id"),
                lock_version=_int(p, "lock_version"),
                result_ref=str(_str(p, "result_ref")),
                succeeded=_bool(p, "succeeded"),
            )
        elif command_type == "frontend.fabric.hook.create":
            item = await self.hooks.create(
                tenant_id=tenant_id,
                project_id=project_id,
                name=str(_str(p, "name")),
                event_kind=str(_str(p, "event_kind")),
                action_kind=str(_str(p, "action_kind")),
                condition=_dict(p, "condition"),
                action_payload=_dict(p, "action_payload"),
                conversation_id=_uuid(p, "conversation_id", optional=True),
                created_by=principal_id,
            )
        elif command_type == "frontend.fabric.hook.set_state":
            item = await self.hooks.set_state(
                tenant_id=tenant_id,
                project_id=project_id,
                hook_id=_uuid(p, "hook_id"),
                lock_version=_int(p, "lock_version"),
                state=str(_str(p, "state")),
            )
        elif command_type == "frontend.fabric.hook.record_trigger":
            item = await self.hooks.record_trigger(
                tenant_id=tenant_id,
                project_id=project_id,
                hook_id=_uuid(p, "hook_id"),
                lock_version=_int(p, "lock_version"),
            )
        elif command_type == "frontend.fabric.claim.annotate":
            item = await self.claims.annotate(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                turn_id=_uuid(p, "turn_id"),
                claim_text=str(_str(p, "claim_text")),
                epistemic_class=str(_str(p, "epistemic_class")),
                source_refs=_strs(p, "source_refs"),
                confidence=_optional_float(p, "confidence"),
                verification_state=str(p.get("verification_state", "UNVERIFIED")),
            )
        elif command_type == "frontend.fabric.experience.record":
            item = await self.experience.record(
                tenant_id=tenant_id,
                project_id=project_id,
                task_signature=_dict(p, "task_signature"),
                worker_configuration=_dict(p, "worker_configuration"),
                outcome=_dict(p, "outcome"),
                economics=_dict(p, "economics"),
                failure_signatures=_strs(p, "failure_signatures"),
                verification_refs=_strs(p, "verification_refs"),
                authority_refs=_strs(p, "authority_refs"),
                mission_id=mission_id,
                task_id=_uuid(p, "task_id", optional=True),
                worker_run_id=_uuid(p, "worker_run_id", optional=True),
                worker_session_id=_uuid(p, "worker_session_id", optional=True),
            )
        elif command_type == "frontend.fabric.insight.propose":
            item = await self.experience.propose_insight(
                tenant_id=tenant_id,
                project_id=project_id,
                source_kind=str(_str(p, "source_kind")),
                source_ref=str(_str(p, "source_ref")),
                proposal=_dict(p, "proposal"),
                evidence_refs=_strs(p, "evidence_refs"),
                confidence=_float(p, "confidence", 0.0),
            )
        elif command_type == "frontend.fabric.insight.advance":
            item = await self.experience.advance_insight(
                tenant_id=tenant_id,
                project_id=project_id,
                insight_id=_uuid(p, "insight_id"),
                target=str(_str(p, "target")),
                lock_version=_int(p, "lock_version"),
                evaluation_refs=_strs(p, "evaluation_refs"),
                principal_id=principal_id,
                promoted_policy_ref=_str(p, "promoted_policy_ref", optional=True),
            )
        else:
            raise DdeError(
                "FORBIDDEN",
                "unknown AI Conversation Fabric command",
                details={"command_type": command_type},
            )
        return {"result": _dump(item), "side_effect_class": "CONTROL_PLANE"}
