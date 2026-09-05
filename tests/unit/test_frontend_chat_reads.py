"""Pure tests for deterministic Frontend Chat read/action routing."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.chat.intent import Classification, Intent
from engine.chat.service import FrontendChatService
from engine.contracts.frontend_conversation import FrontendConversation
from engine.studio.audit.reads import ScreenAuditReadService
from engine.studio.inspector import InspectorService
from engine.studio.locks.service import LockService
from engine.studio.reads import FrontendReadService
from engine.studio.source.service import SourceIntelligenceService


class _Reads:
    async def snapshot(self, **_: object) -> SimpleNamespace:
        candidate = SimpleNamespace(
            candidate_id=str(CANDIDATE_ID),
            state="VERIFIED",
            workspace_id="workspace-1",
            preview_session_id="preview-1",
            preview_state="LIVE",
            verification_request_state="PASSED",
            verification_run_id="run-1",
            verification_run_status="PASSED",
        )
        return SimpleNamespace(
            pxg_revision=7,
            contract_version=3,
            candidates=SimpleNamespace(cards=(candidate,)),
            coverage=SimpleNamespace(
                summary_state="PARTIAL",
                weighted_percent=None,
                blocking_finding_count=2,
                dimension_states=(("screen", "ASSESSED"), ("journey", "PARTIAL")),
                reason="journey evidence incomplete",
                stale=False,
                availability=SimpleNamespace(value="AVAILABLE"),
            ),
        )

    async def candidate_board(self, **_: object) -> SimpleNamespace:
        return SimpleNamespace(
            cards=(
                SimpleNamespace(
                    candidate_id=str(CANDIDATE_ID),
                    verification_request_state="PASSED",
                    verification_run_status="PASSED",
                    verification_evidence_refs=("ev-1", "ev-2"),
                    verification_checks=(
                        SimpleNamespace(kind="silhouette", status="PASSED"),
                        SimpleNamespace(kind="visual_critique", status="PASSED"),
                    ),
                ),
            )
        )


class _Locks:
    async def active(self, **_: object) -> tuple[SimpleNamespace, ...]:
        return (
            SimpleNamespace(
                lock_id=uuid4(), lock_kind="SECTION", scope_key="screens/checkout"
            ),
        )


class _Inspector:
    async def describe(self, **_: object) -> SimpleNamespace:
        return SimpleNamespace(
            title="Checkout hero",
            node_kind="region",
            candidate_state="VERIFIED",
            source_mapping="VERIFIED",
            properties=(SimpleNamespace(property_name="spacing"),),
            required_verification=("silhouette", "visual_critique"),
        )


class _AuditReads:
    async def current_findings(self, **_: object) -> tuple[SimpleNamespace, ...]:
        return (
            SimpleNamespace(
                finding_type="MISSING_ERROR_STATE",
                pxg_key="screens/checkout",
                node_key=None,
                severity="BLOCKING",
                assessment_state="FAIL",
            ),
        )


class _Sources:
    async def search(self, **_: object) -> SimpleNamespace:
        return SimpleNamespace(
            run=SimpleNamespace(
                status="PARTIAL", degradation={"21st": {"status": "NOT_CONFIGURED"}}
            ),
            artifacts=(SimpleNamespace(title="Checkout Hero", artifact_id=uuid4()),),
        )


CANDIDATE_ID = uuid4()


def _service() -> FrontendChatService:
    return FrontendChatService(
        cast(AsyncEngine, object()),
        reads=cast(FrontendReadService, _Reads()),
        inspector=cast(InspectorService, _Inspector()),
        locks=cast(LockService, _Locks()),
        audit_reads=cast(ScreenAuditReadService, _AuditReads()),
        sources=cast(SourceIntelligenceService, _Sources()),
    )


def _conversation(*, candidate: bool = True) -> FrontendConversation:
    now = datetime.now(UTC)
    return FrontendConversation(
        conversation_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        mission_id=uuid4(),
        active_candidate_id=CANDIDATE_ID if candidate else None,
        design_session_id=None,
        screen_key="screens/checkout",
        selected_node_keys=["screens/checkout#hero"],
        viewport="1440",
        status="OPEN",
        mode="ASK",
        pinned_context_refs=[],
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_coverage_query_answers_from_the_real_projection_shape() -> None:
    outcome, code, detail, message = await _service()._route_read_or_explicit_action(
        tenant_id=uuid4(),
        project_id=uuid4(),
        conversation=_conversation(),
        classification=Classification(intent=Intent.COVERAGE_QUERY),
        text="how much coverage do we have?",
    )
    assert (outcome, code, detail) == ("ANSWERED", None, None)
    assert "Coverage PARTIAL" in message
    assert "percentage unavailable" in message
    assert "blocking findings=2" in message
    assert "journey=PARTIAL" in message


@pytest.mark.asyncio
async def test_qa_query_reports_current_candidate_verification_evidence() -> None:
    outcome, code, detail, message = await _service()._route_read_or_explicit_action(
        tenant_id=uuid4(),
        project_id=uuid4(),
        conversation=_conversation(),
        classification=Classification(intent=Intent.QA_QUERY),
        text="show QA findings",
    )
    assert (outcome, code, detail) == ("ANSWERED", None, None)
    assert "Screen Audit: 1 unresolved finding(s); blocking=1" in message
    assert "MISSING_ERROR_STATE@screens/checkout [BLOCKING/FAIL]" in message
    assert "active candidate verification=PASSED" in message


@pytest.mark.asyncio
async def test_inspect_query_uses_the_governed_inspector_descriptor() -> None:
    outcome, code, detail, message = await _service()._route_read_or_explicit_action(
        tenant_id=uuid4(),
        project_id=uuid4(),
        conversation=_conversation(),
        classification=Classification(
            intent=Intent.INSPECT, target_keys=("screens/checkout#hero",)
        ),
        text="inspect hero",
    )
    assert (outcome, code, detail) == ("ANSWERED", None, None)
    assert "Checkout hero (region)" in message
    assert "source=VERIFIED" in message
    assert "editable properties: spacing" in message


@pytest.mark.asyncio
async def test_source_search_uses_governed_m8_projection_and_reports_degradation() -> (
    None
):
    outcome, code, detail, message = await _service()._route_read_or_explicit_action(
        tenant_id=uuid4(),
        project_id=uuid4(),
        conversation=_conversation(),
        classification=Classification(intent=Intent.SEARCH_SOURCE),
        text="find checkout components",
    )
    assert (outcome, code, detail) == ("ANSWERED", None, None)
    assert "Source search PARTIAL: 1 result(s)" in message
    assert "Checkout Hero" in message
    assert "degraded providers: 21st" in message


@pytest.mark.asyncio
@pytest.mark.parametrize("intent", [Intent.LOCK_CHANGE, Intent.PROMOTE])
async def test_chat_does_not_bypass_explicit_authority_surfaces(intent: Intent) -> None:
    outcome, code, detail, message = await _service()._route_read_or_explicit_action(
        tenant_id=uuid4(),
        project_id=uuid4(),
        conversation=_conversation(),
        classification=Classification(intent=intent),
        text="change authority state",
    )
    assert outcome == "REFUSED"
    assert code == "EXPLICIT_CONTROL_REQUIRED"
    assert detail == message


@pytest.mark.asyncio
async def test_turn_context_snapshot_is_resolved_from_core_authorities() -> None:
    conversation = _conversation()
    context = await _service()._context_snapshot(
        tenant_id=conversation.tenant_id,
        project_id=conversation.project_id,
        conversation=conversation,
    )
    assert context["pxg_revision"] == 7
    assert context["contract_version"] == 3
    assert context["coverage"] == {
        "state": "PARTIAL",
        "stale": False,
        "availability": "AVAILABLE",
    }
    assert context["selected_node_keys"] == ["screens/checkout#hero"]
    candidate = cast(dict[str, object], context["candidate"])
    locks = cast(list[dict[str, object]], context["active_locks"])
    assert candidate["verification_run_status"] == "PASSED"
    assert candidate["preview_state"] == "LIVE"
    assert locks[0]["scope_key"] == "screens/checkout"
