"""Mission-scoped command facade for universal DDE Chat.

This is the canonical command surface for ``dde.chat.*``. It depends only on
DDE Chat domain services and shared workspace authority. Frontend Studio uses
the same domain through its optional context adapter; it is not the owner of
conversation history, plans, attachments, checkpoints, provider sessions, or
workspace review.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.chat.activity import FrontendChatActivityService
from engine.chat.attachments import FrontendChatAttachmentService
from engine.chat.checkpoints import FrontendChatCheckpointService
from engine.chat.context_refs import FrontendChatContextService
from engine.chat.plans import FrontendChatPlanService
from engine.chat.service import FrontendChatService
from engine.chat.workspace_review import (
    FrontendChatWorkspaceReviewService,
    WorkspaceChanges,
)
from engine.core.errors import DdeError


class DdeChatCommandFacade:
    """Map canonical ``dde.chat.*`` commands onto DDE-owned Chat services."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.activities = FrontendChatActivityService(engine)
        self.attachments = FrontendChatAttachmentService(
            engine, activities=self.activities
        )
        self.plans = FrontendChatPlanService(engine, activities=self.activities)
        self.review = FrontendChatWorkspaceReviewService(
            engine, activities=self.activities
        )
        self.checkpoints = FrontendChatCheckpointService(
            engine,
            attachments=self.attachments,
            workspace_review=self.review,
            activities=self.activities,
        )
        self.context = FrontendChatContextService(
            engine, attachments=self.attachments, plans=self.plans
        )
        self.chat = FrontendChatService(
            engine,
            attachments=self.attachments,
            plans=self.plans,
            activities=self.activities,
            context=self.context,
        )

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
        if command_type.startswith("frontend.chat."):
            command_type = command_type.replace("frontend.chat.", "dde.chat.", 1)
        p = parameters
        item: Any
        if command_type == "dde.chat.open":
            context_domain = _optional_str(p, "context_domain")
            if context_domain is None:
                context_domain = (
                    "FRONTEND_STUDIO"
                    if p.get("screen_key") is not None
                    or p.get("active_candidate_id") is not None
                    else "MISSION"
                )
            item = await self.chat.open(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                screen_key=_optional_str(p, "screen_key"),
                viewport=str(p.get("viewport") or "desktop-1440"),
                title=_optional_str(p, "title"),
                mode=str(p.get("mode") or "ASK"),
                model_profile_id=_optional_str(p, "model_profile_id"),
                active_workspace_id=_optional_uuid(p, "active_workspace_id"),
                context_domain=context_domain,
                active_task_id=_optional_uuid(p, "active_task_id"),
                active_worker_run_id=_optional_uuid(p, "active_worker_run_id"),
                active_verification_run_id=_optional_uuid(
                    p, "active_verification_run_id"
                ),
                active_artifact_ref=_optional_str(p, "active_artifact_ref"),
                created_by=principal_id,
            )
            return _conversation_payload(item)

        if command_type == "dde.chat.set_context":
            raw_keys = p.get("selected_node_keys")
            item = await self.chat.set_context(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                selected_node_keys=(
                    _string_list(p, "selected_node_keys")
                    if raw_keys is not None
                    else None
                ),
                active_candidate_id=_optional_uuid(p, "active_candidate_id"),
                set_active_candidate="active_candidate_id" in p,
                screen_key=_optional_str(p, "screen_key"),
                set_screen="screen_key" in p,
                viewport=_optional_str(p, "viewport"),
                active_workspace_id=_optional_uuid(p, "active_workspace_id"),
                set_active_workspace="active_workspace_id" in p,
                context_domain=_optional_str(p, "context_domain"),
                set_context_domain="context_domain" in p,
                active_task_id=_optional_uuid(p, "active_task_id"),
                set_active_task="active_task_id" in p,
                active_worker_run_id=_optional_uuid(p, "active_worker_run_id"),
                set_active_worker_run="active_worker_run_id" in p,
                active_verification_run_id=_optional_uuid(
                    p, "active_verification_run_id"
                ),
                set_active_verification_run="active_verification_run_id" in p,
                active_artifact_ref=_optional_str(p, "active_artifact_ref"),
                set_active_artifact="active_artifact_ref" in p,
            )
            return _conversation_payload(item)

        if command_type == "dde.chat.send":
            result = await self.chat.send(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                text=_str(p, "text"),
                attachment_ids=tuple(
                    _uuid_value(v, "attachment_ids") for v in _list(p, "attachment_ids")
                ),
                approval_id=_optional_uuid(p, "approval_id"),
            )
            return {
                "turn_id": str(result.turn.turn_id),
                "reply_turn_id": str(result.reply.turn_id),
                "sequence": result.turn.sequence,
                "intent": result.turn.intent,
                "outcome": result.turn.outcome,
                "refusal_code": result.turn.refusal_code,
                "refusal_detail": result.turn.refusal_detail,
                "resolved_context": result.turn.resolved_context,
                "produced_refs": list(result.produced_refs),
                "message": result.message,
                "side_effect_class": "WORKSPACE_LOCAL",
            }

        if command_type == "dde.chat.rename":
            item = await self.chat.rename(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                title=_str(p, "title"),
            )
            return _conversation_payload(item)
        if command_type == "dde.chat.archive":
            item = await self.chat.archive(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                archived=_bool(p, "archived", True),
            )
            return _conversation_payload(item)
        if command_type == "dde.chat.set_mode":
            item = await self.chat.set_mode(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                mode=_str(p, "mode"),
            )
            return _conversation_payload(item)
        if command_type == "dde.chat.set_model":
            item = await self.chat.set_model(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                model_profile_id=_optional_str(p, "model_profile_id"),
            )
            return _conversation_payload(item)
        if command_type == "dde.chat.pin_context":
            item = await self.chat.pin_context(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                context_ref=_str(p, "context_ref"),
                pinned=_bool(p, "pinned"),
            )
            return _conversation_payload(item)
        if command_type == "dde.chat.branch":
            item = await self.chat.branch(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                from_turn_id=_optional_uuid(p, "from_turn_id"),
                created_by=principal_id,
                title=_optional_str(p, "title"),
            )
            return _conversation_payload(item)

        if command_type == "dde.chat.attachment.reserve":
            item = await self.attachments.reserve(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                filename=_str(p, "filename"),
                media_type=str(p.get("media_type") or "application/octet-stream"),
                size_bytes=_int(p, "size_bytes"),
                created_by=principal_id,
            )
            return _model_payload("attachment", item)
        if command_type == "dde.chat.attachment.import_workspace":
            item = await self.attachments.import_workspace_file(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                workspace_id=_uuid(p, "workspace_id"),
                relative_path=_str(p, "relative_path"),
                created_by=principal_id,
            )
            return _model_payload("attachment", item)
        if command_type == "dde.chat.attachment.remove":
            item = await self.attachments.remove(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                attachment_id=_uuid(p, "attachment_id"),
            )
            return _model_payload("attachment", item)

        if command_type == "dde.chat.plan.create":
            item = await self.plans.create(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=mission_id,
                conversation_id=_uuid(p, "conversation_id"),
                title=_str(p, "title"),
                objective=_str(p, "objective"),
                steps=_rows(p, "steps"),
                approval_required=_bool(p, "approval_required", True),
                workspace_id=_optional_uuid(p, "workspace_id"),
                task_graph_id=_optional_uuid(p, "task_graph_id"),
                context_snapshot=_optional_dict(p, "context_snapshot"),
            )
            return _model_payload("plan", item)
        if command_type == "dde.chat.plan.update":
            item = await self.plans.update(
                tenant_id=tenant_id,
                project_id=project_id,
                plan_id=_uuid(p, "plan_id"),
                expected_lock_version=_int(p, "lock_version"),
                title=_optional_str(p, "title"),
                objective=_optional_str(p, "objective"),
                steps=_rows(p, "steps") if "steps" in p else None,
            )
            return _model_payload("plan", item)
        if command_type == "dde.chat.plan.approve":
            item = await self.plans.approve(
                tenant_id=tenant_id,
                project_id=project_id,
                plan_id=_uuid(p, "plan_id"),
                principal_id=principal_id,
                expected_lock_version=_int(p, "lock_version"),
            )
            return _model_payload("plan", item)
        if command_type == "dde.chat.plan.prepare_step":
            item = await self.plans.prepare_step(
                tenant_id=tenant_id,
                project_id=project_id,
                plan_id=_uuid(p, "plan_id"),
                step_id=_uuid(p, "step_id"),
                protocol_version=str(p.get("protocol_version") or "1"),
            )
            return {**item, "side_effect_class": "WORKSPACE_LOCAL"}
        if command_type == "dde.chat.plan.record_step":
            item = await self.plans.record_step(
                tenant_id=tenant_id,
                project_id=project_id,
                plan_id=_uuid(p, "plan_id"),
                step_id=_uuid(p, "step_id"),
                command_id=_uuid(p, "command_id"),
            )
            return _model_payload("plan", item)
        if command_type == "dde.chat.plan.retry_step":
            item = await self.plans.retry_step(
                tenant_id=tenant_id,
                project_id=project_id,
                plan_id=_uuid(p, "plan_id"),
                step_id=_uuid(p, "step_id"),
            )
            return _model_payload("plan", item)
        if command_type == "dde.chat.plan.cancel":
            item = await self.plans.cancel(
                tenant_id=tenant_id,
                project_id=project_id,
                plan_id=_uuid(p, "plan_id"),
                expected_lock_version=_int(p, "lock_version"),
            )
            return _model_payload("plan", item)

        if command_type == "dde.chat.activity.cancel":
            item = await self.activities.cancel(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                activity_id=_uuid(p, "activity_id"),
                reason=_str(p, "reason"),
            )
            return _model_payload("activity", item)
        if command_type == "dde.chat.checkpoint.create":
            item = await self.checkpoints.create(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                created_by=principal_id,
                note=_optional_str(p, "note"),
            )
            return _model_payload("checkpoint", item)
        if command_type == "dde.chat.checkpoint.restore":
            item = await self.checkpoints.restore_context(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                checkpoint_id=_uuid(p, "checkpoint_id"),
            )
            return _conversation_payload(item)

        if command_type == "dde.chat.workspace.apply_patch":
            item = await self.review.apply_patch(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                patch_text=_str(p, "patch_text"),
                expected_diff_hash=_optional_str(p, "expected_diff_hash"),
            )
            return _changes_payload(item)
        if command_type == "dde.chat.workspace.accept_file":
            item = await self.review.accept_file(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                path=_str(p, "path"),
                expected_diff_hash=_str(p, "expected_diff_hash"),
                principal_id=principal_id,
            )
            return _model_payload("review", item)
        if command_type == "dde.chat.workspace.revert_file":
            item = await self.review.revert_file(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                path=_str(p, "path"),
                expected_diff_hash=_str(p, "expected_diff_hash"),
                principal_id=principal_id,
            )
            return _changes_payload(item)
        if command_type == "dde.chat.workspace.revert_all":
            item = await self.review.revert_all(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=_uuid(p, "conversation_id"),
                checkpoint_id=_uuid(p, "checkpoint_id"),
                principal_id=principal_id,
            )
            return _changes_payload(item)

        raise DdeError(
            "FORBIDDEN",
            "unsupported DDE Chat command",
            details={"command_type": command_type},
        )


def _model_payload(key: str, value: BaseModel) -> dict[str, object]:
    return {
        key: value.model_dump(mode="json"),
        "side_effect_class": "WORKSPACE_LOCAL",
    }


def _conversation_payload(value: BaseModel) -> dict[str, object]:
    return {
        "conversation": value.model_dump(mode="json"),
        "side_effect_class": "WORKSPACE_LOCAL",
    }


def _changes_payload(value: WorkspaceChanges) -> dict[str, object]:
    return {
        "changes": {
            "workspace_id": str(value.workspace_id),
            "base_revision": value.base_revision,
            "workspace_revision": value.workspace_revision,
            "diff_hash": value.diff_hash,
            "changes": [asdict(item) for item in value.changes],
        },
        "side_effect_class": "WORKSPACE_LOCAL",
    }


def _str(parameters: dict[str, object], name: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str) or not value.strip():
        raise DdeError("VALIDATION_FAILED", f"'{name}' must be a non-empty string")
    return value.strip()


def _optional_str(parameters: dict[str, object], name: str) -> str | None:
    value = parameters.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise DdeError("VALIDATION_FAILED", f"'{name}' must be a string or null")
    clean = value.strip()
    return clean or None


def _uuid_value(value: object, name: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError) as exc:
        raise DdeError(
            "VALIDATION_FAILED", f"'{name}' must contain UUID values"
        ) from exc


def _uuid(parameters: dict[str, object], name: str) -> UUID:
    if name not in parameters:
        raise DdeError("VALIDATION_FAILED", f"'{name}' is required")
    return _uuid_value(parameters[name], name)


def _optional_uuid(parameters: dict[str, object], name: str) -> UUID | None:
    value = parameters.get(name)
    return None if value is None else _uuid_value(value, name)


def _int(parameters: dict[str, object], name: str) -> int:
    value = parameters.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise DdeError("VALIDATION_FAILED", f"'{name}' must be an integer")
    return value


def _bool(
    parameters: dict[str, object], name: str, default: bool | None = None
) -> bool:
    value = parameters.get(name)
    if value is None and default is not None:
        return default
    if not isinstance(value, bool):
        raise DdeError("VALIDATION_FAILED", f"'{name}' must be a boolean")
    return value


def _list(parameters: dict[str, object], name: str) -> list[object]:
    value = parameters.get(name, [])
    if not isinstance(value, list):
        raise DdeError("VALIDATION_FAILED", f"'{name}' must be a list")
    return list(value)


def _string_list(parameters: dict[str, object], name: str) -> list[str]:
    values = _list(parameters, name)
    if not all(isinstance(item, str) for item in values):
        raise DdeError("VALIDATION_FAILED", f"'{name}' must contain strings")
    return [str(item) for item in values]


def _rows(parameters: dict[str, object], name: str) -> list[dict[str, object]]:
    values = _list(parameters, name)
    if not all(isinstance(item, dict) for item in values):
        raise DdeError("VALIDATION_FAILED", f"'{name}' must contain objects")
    return [dict(item) for item in values if isinstance(item, dict)]


def _optional_dict(
    parameters: dict[str, object], name: str
) -> dict[str, object] | None:
    value = parameters.get(name)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise DdeError("VALIDATION_FAILED", f"'{name}' must be an object or null")
    return dict(value)
