from __future__ import annotations

from pathlib import Path

import pytest

from engine.events.service import EventService
from engine.missions.service import MissionService
from engine.chat.activity import FrontendChatActivityService
from engine.chat.attachments import FrontendChatAttachmentService
from engine.chat.plans import FrontendChatPlanService
from engine.chat.service import FrontendChatService
from engine.chat.storage import ChatObjectStore
from tests.support.db import new_engine, seed_tenant


@pytest.mark.asyncio
async def test_cursor_chat_persists_history_attachment_plan_and_branch(
    tmp_path: Path,
) -> None:
    engine = new_engine()
    try:
        fixture = await seed_tenant(engine)
        missions = MissionService(engine, EventService(engine))
        mission = await missions.create_mission(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            slug=f"CURSOR-CHAT-{fixture.project_id.hex[:12]}",
            title="Cursor-class Chat",
            intent="Prove durable AI chat state",
            success_definition="History, attachments, plans and branches persist",
            scope=["frontend"],
            requirement_refs=[],
            autonomy_ceiling=2,
        )
        activities = FrontendChatActivityService(engine)
        attachments = FrontendChatAttachmentService(
            engine, store=ChatObjectStore(root=tmp_path), activities=activities
        )
        plans = FrontendChatPlanService(engine, activities=activities)
        chat = FrontendChatService(
            engine, attachments=attachments, plans=plans, activities=activities
        )
        conversation = await chat.open(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            title="Primary thread",
            mode="PLAN",
            created_by=fixture.principal_id,
        )
        renamed = await chat.rename(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            conversation_id=conversation.conversation_id,
            title="Checkout implementation",
        )
        assert renamed.mode == "PLAN"

        reserved = await attachments.reserve(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            conversation_id=conversation.conversation_id,
            filename="requirements.md",
            media_type="text/markdown",
            size_bytes=5,
            created_by=fixture.principal_id,
        )
        uploaded = await attachments.complete_upload(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            conversation_id=conversation.conversation_id,
            attachment_id=reserved.attachment_id,
            content=b"hello",
        )
        assert uploaded.status == "ACTIVE"
        assert uploaded.extraction_state == "EXTRACTED"

        plan = await plans.create(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            conversation_id=conversation.conversation_id,
            title="Set spacing",
            objective="Change the selected spacing token",
            steps=[
                {
                    "title": "Apply token",
                    "command_type": "frontend.mutation.apply",
                    "parameters": {"candidate_id": "candidate", "mutations": []},
                }
            ],
            approval_required=True,
        )
        assert plan.state == "READY"
        branch = await chat.branch(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            conversation_id=conversation.conversation_id,
            from_turn_id=None,
            created_by=fixture.principal_id,
            title="Alternative",
        )
        assert branch.parent_conversation_id == conversation.conversation_id
        listed = await chat.list_conversations(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            mission_id=mission.mission_id,
            include_archived=True,
        )
        assert {item.conversation_id for item in listed} >= {
            conversation.conversation_id,
            branch.conversation_id,
        }
        stored_attachments = await attachments.list_for_conversation(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            conversation_id=conversation.conversation_id,
        )
        stored_plans = await plans.list_for_conversation(
            tenant_id=fixture.tenant_id,
            project_id=fixture.project_id,
            conversation_id=conversation.conversation_id,
        )
        assert stored_attachments[0].content_hash == uploaded.content_hash
        assert stored_plans[0].plan_id == plan.plan_id
    finally:
        await engine.dispose()
