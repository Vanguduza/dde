# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendConversation(BaseModel):
    """
    DDE-069 universal DDE Chat durable conversation control plane. Canonical domain
    owner: engine.chat. It carries mission/task/workspace/worker/verification/artifact
    context for every DDE workspace, with Frontend Studio candidate/screen/PXG selection
    as an optional context adapter. Cursor-class Ask/Plan/Execute, model/provider
    selection, branch lineage and pinned references are DDE-owned and provider-
    replaceable.
    """

    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    active_candidate_id: UUID | None = None
    design_session_id: UUID | None = None
    screen_key: str | None = None
    selected_node_keys: list[str]
    viewport: str
    title: str | None = None
    status: Literal["OPEN", "ARCHIVED"]
    mode: Literal["ASK", "PLAN", "EXECUTE"]
    model_profile_id: str | None = None
    active_workspace_id: UUID | None = None
    active_plan_id: UUID | None = None
    parent_conversation_id: UUID | None = None
    branched_from_turn_id: UUID | None = None
    pinned_context_refs: list[str]
    created_by: UUID | None = None
    archived_at: datetime | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime
    policy_id: UUID | None = None
    active_worker_session_id: UUID | None = None
    context_domain: (
        Literal[
            "DDE",
            "MISSION",
            "TASK",
            "FRONTEND_STUDIO",
            "QUALITY",
            "RESEARCH",
            "DECISIONS",
            "FLEET",
            "EVIDENCE",
        ]
        | None
    ) = None
    active_task_id: UUID | None = None
    active_worker_run_id: UUID | None = None
    active_verification_run_id: UUID | None = None
    active_artifact_ref: str | None = None
