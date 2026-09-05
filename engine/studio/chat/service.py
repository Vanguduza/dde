"""DDE-069 Frontend Chat service.

Sole writer of `frontend_conversations` and
`frontend_conversation_turns`. Turns are append-only, and each records the
intent it was classified as, the context its references resolved against
and the ids of whatever it produced -- so the line from "make the hero
roomier" to the mutation that changed the hero is reconstructable later.

Routing is the point. A deterministic edit compiles to the same
`MutationRequest` the inspector produces and goes through the same
planner, locks and staleness checks. A design-class intent goes to the
DesignGateway. Neither path is special-cased, and there is no third path
that writes frontend state directly from chat.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_conversation import FrontendConversation
from engine.contracts.frontend_conversation_turn import FrontendConversationTurn
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.chat.intent import (
    DESIGN_INTENTS,
    ChatContext,
    Classification,
    Intent,
    classify,
)
from engine.studio.design.gateway import DesignGateway
from engine.studio.inspector import InspectorService
from engine.studio.locks.service import LockService
from engine.studio.mutations.governed import GovernedMutationService
from engine.studio.mutations.planner import MutationRequest
from engine.studio.reads import FrontendReadService
from engine.studio.tables import frontend_conversation_turns, frontend_conversations
from engine.truth.db import open_unit_of_work


@dataclass(frozen=True)
class TurnResult:
    """The persisted user turn plus the Studio reply rendered by the composer."""

    turn: FrontendConversationTurn
    reply: FrontendConversationTurn
    classification: Classification
    produced_refs: tuple[str, ...]
    message: str


class FrontendChatService:
    """The shared conversational control plane."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        mutations: GovernedMutationService | None = None,
        design: DesignGateway | None = None,
        reads: FrontendReadService | None = None,
        inspector: InspectorService | None = None,
        locks: LockService | None = None,
    ) -> None:
        self._engine = engine
        self._mutations = mutations or GovernedMutationService(engine)
        self._design = design or DesignGateway(engine)
        self._reads = reads or FrontendReadService(engine)
        self._inspector = inspector or InspectorService(engine)
        self._locks = locks or LockService(engine)

    async def open(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID | None = None,
        screen_key: str | None = None,
        viewport: str = "desktop-1440",
    ) -> FrontendConversation:
        now = datetime.now(UTC)
        record = FrontendConversation(
            conversation_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            active_candidate_id=None,
            design_session_id=None,
            screen_key=screen_key,
            selected_node_keys=[],
            viewport=viewport,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                frontend_conversations.insert().values(
                    **record.model_dump(exclude={"selected_node_keys"}),
                    selected_node_keys=[],
                )
            )
            await uow.commit()
        return record

    async def set_context(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        selected_node_keys: list[str] | None = None,
        active_candidate_id: UUID | None = None,
        set_active_candidate: bool = False,
        screen_key: str | None = None,
        set_screen: bool = False,
        viewport: str | None = None,
    ) -> FrontendConversation:
        """Update what the conversation is about.

        The selection lives on the conversation so a later turn saying
        "this" resolves to what the user actually had selected, rather
        than to whatever the client happened to send with that turn.
        """
        now = datetime.now(UTC)
        values: dict[str, object] = {"updated_at": now}
        if selected_node_keys is not None:
            values["selected_node_keys"] = selected_node_keys
        if set_active_candidate:
            values["active_candidate_id"] = active_candidate_id
        if set_screen:
            values["screen_key"] = screen_key
        if viewport is not None:
            values["viewport"] = viewport
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                update(frontend_conversations)
                .where(
                    frontend_conversations.c.conversation_id == conversation_id,
                    frontend_conversations.c.tenant_id == tenant_id,
                    frontend_conversations.c.project_id == project_id,
                )
                .values(**values)
                .returning(frontend_conversations)
            )
            row = result.mappings().first()
            if row is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "unknown conversation in this project",
                    retryable=False,
                    details={"conversation_id": str(conversation_id)},
                )
            await uow.commit()
        return FrontendConversation.model_validate(dict(row))

    async def send(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        text: str,
    ) -> TurnResult:
        """Classify a turn, route it, and record what happened."""
        conversation = await self._conversation(
            tenant_id=tenant_id, project_id=project_id, conversation_id=conversation_id
        )
        context = ChatContext(
            selected_node_keys=tuple(conversation.selected_node_keys),
            active_candidate_id=(
                str(conversation.active_candidate_id)
                if conversation.active_candidate_id
                else None
            ),
            screen_key=conversation.screen_key,
            viewport=conversation.viewport,
        )
        classification = classify(text, context)
        context_snapshot = await self._context_snapshot(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation=conversation,
        )

        produced: tuple[str, ...] = ()
        outcome = "ANSWERED"
        refusal_code = classification.refusal_code
        refusal_detail = classification.refusal_detail
        message = ""

        if refusal_code is not None:
            outcome = "REFUSED"
            message = refusal_detail or "the studio could not act on that"
        elif classification.intent is Intent.MUTATE_DETERMINISTIC:
            (
                outcome,
                refusal_code,
                refusal_detail,
                produced,
                message,
            ) = await self._route_mutation(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation=conversation,
                classification=classification,
            )
        elif classification.intent is Intent.UNDO_REVERT:
            (
                outcome,
                refusal_code,
                refusal_detail,
                produced,
                message,
            ) = await self._route_revert(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation=conversation,
            )
        elif classification.intent in DESIGN_INTENTS:
            (
                outcome,
                refusal_code,
                refusal_detail,
                produced,
                message,
            ) = await self._route_design(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation=conversation,
                classification=classification,
                text=text,
            )
        elif classification.intent in {
            Intent.COVERAGE_QUERY,
            Intent.QA_QUERY,
            Intent.INSPECT,
            Intent.SEARCH_SOURCE,
            Intent.EXPLAIN,
            Intent.LOCK_CHANGE,
            Intent.PROMOTE,
        }:
            (
                outcome,
                refusal_code,
                refusal_detail,
                message,
            ) = await self._route_read_or_explicit_action(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation=conversation,
                classification=classification,
            )
        elif classification.intent is Intent.UNKNOWN:
            outcome = "REFUSED"
            refusal_code = "INTENT_AMBIGUOUS"
            refusal_detail = (
                "the studio could not tell what this instruction should do; "
                "rephrase it as an edit, a question or a /design request"
            )
            message = refusal_detail
        else:
            # Read-only intents are answered from projections elsewhere;
            # the turn records the classification so the caller can serve
            # it without re-parsing.
            message = f"classified as {classification.intent.value}"

        turn = await self._append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            role="user",
            text=text,
            classification=classification,
            outcome=outcome,
            refusal_code=refusal_code,
            refusal_detail=refusal_detail,
            produced=produced,
            context_snapshot=context_snapshot,
        )
        reply = await self._append(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation_id,
            role="studio",
            text=message,
            classification=classification,
            outcome=outcome,
            refusal_code=refusal_code,
            refusal_detail=refusal_detail,
            produced=produced,
            context_snapshot=context_snapshot,
        )
        return TurnResult(
            turn=turn,
            reply=reply,
            classification=classification,
            produced_refs=produced,
            message=message,
        )

    async def _route_mutation(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
        classification: Classification,
    ) -> tuple[str, str | None, str | None, tuple[str, ...], str]:
        if conversation.active_candidate_id is None:
            return (
                "REFUSED",
                "NO_ACTIVE_CANDIDATE",
                "chat edits apply to a candidate; none is active. The "
                "accepted design is never edited in place.",
                (),
                "no active candidate",
            )
        if classification.mutation is None:
            return (
                "REFUSED",
                "INTENT_AMBIGUOUS",
                "no deterministic mutation could be compiled from the message",
                (),
                "nothing to apply",
            )
        payload = classification.mutation["payload"]
        requests = [
            MutationRequest(
                operation=str(classification.mutation["operation"]),
                target_key=key,
                origin="CHAT",
                payload=dict(payload) if isinstance(payload, dict) else {},
            )
            for key in classification.target_keys
        ]
        governed = await self._mutations.apply(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=conversation.active_candidate_id,
            requests=requests,
        )
        result = governed.mutation
        produced = tuple(str(item.mutation_id) for item in result.applied)
        if result.applied and not result.refused:
            return (
                "ROUTED",
                None,
                None,
                produced,
                f"applied {len(result.applied)} change(s)",
            )
        if not result.applied:
            first = result.refused[0]
            return (
                "REFUSED",
                first.refusal_code,
                first.refusal_detail,
                (),
                first.refusal_detail or "refused",
            )
        first = result.refused[0]
        return (
            "ROUTED",
            first.refusal_code,
            first.refusal_detail,
            produced,
            f"applied {len(result.applied)}, refused {len(result.refused)}",
        )

    async def _route_read_or_explicit_action(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
        classification: Classification,
    ) -> tuple[str, str | None, str | None, str]:
        intent = classification.intent
        if intent is Intent.COVERAGE_QUERY:
            snapshot = await self._reads.snapshot(
                tenant_id=tenant_id, project_id=project_id
            )
            coverage = snapshot.coverage
            percent = (
                f"{round(coverage.weighted_percent)}%"
                if coverage.weighted_percent is not None
                else "percentage unavailable"
            )
            dimensions = ", ".join(
                f"{dimension}={state}" for dimension, state in coverage.dimension_states
            )
            message = (
                f"Coverage {coverage.summary_state}: {percent}; "
                f"blocking findings={coverage.blocking_finding_count}"
            )
            if dimensions:
                message += f"; dimensions: {dimensions}"
            if coverage.reason:
                message += f"; {coverage.reason}"
            return "ANSWERED", None, None, message

        if intent is Intent.QA_QUERY:
            if conversation.active_candidate_id is None:
                detail = (
                    "QA query needs an active candidate to identify current evidence"
                )
                return "REFUSED", "NO_ACTIVE_CANDIDATE", detail, detail
            board = await self._reads.candidate_board(
                tenant_id=tenant_id, project_id=project_id
            )
            candidate_id = str(conversation.active_candidate_id)
            card = next(
                (item for item in board.cards if item.candidate_id == candidate_id),
                None,
            )
            if card is None:
                detail = (
                    "the active candidate is absent from the current candidate board"
                )
                return "REFUSED", "CONTEXT_INCOMPLETE", detail, detail
            checks = ", ".join(
                f"{item.kind}={item.status}" for item in card.verification_checks
            )
            run_state = card.verification_run_status or "NOT_EVALUATED"
            request_state = card.verification_request_state or "NOT_REQUESTED"
            message = (
                f"Candidate QA: request={request_state}; run={run_state}; "
                f"evidence={len(card.verification_evidence_refs)}"
            )
            if checks:
                message += f"; checks: {checks}"
            return "ANSWERED", None, None, message

        if intent is Intent.INSPECT:
            if conversation.active_candidate_id is None:
                detail = "inspection needs an active candidate; none is selected"
                return "REFUSED", "NO_ACTIVE_CANDIDATE", detail, detail
            if not classification.target_keys:
                detail = "inspection needs one stable selected PXG key"
                return "REFUSED", "AMBIGUOUS_REFERENCE", detail, detail
            descriptor = await self._inspector.describe(
                tenant_id=tenant_id,
                project_id=project_id,
                candidate_id=conversation.active_candidate_id,
                pxg_key=classification.target_keys[0],
            )
            properties = ", ".join(item.property_name for item in descriptor.properties)
            verification = ", ".join(descriptor.required_verification)
            message = (
                f"{descriptor.title} ({descriptor.node_kind}); "
                f"candidate={descriptor.candidate_state}; "
                f"source={descriptor.source_mapping}"
            )
            if properties:
                message += f"; editable properties: {properties}"
            if verification:
                message += f"; required verification: {verification}"
            return "ANSWERED", None, None, message

        if intent is Intent.SEARCH_SOURCE:
            detail = (
                "Source Intelligence (DDE-069 M8) is not implemented; "
                "the studio will not fabricate source search results"
            )
            return "REFUSED", "CAPABILITY_UNAVAILABLE", detail, detail

        if intent is Intent.LOCK_CHANGE:
            detail = (
                "lock changes require the explicit governed lock control so creator/"
                "release authority is attributable; Chat will not invent that principal"
            )
            return "REFUSED", "EXPLICIT_CONTROL_REQUIRED", detail, detail

        if intent is Intent.PROMOTE:
            detail = (
                "promotion requires the explicit candidate promotion control and its "
                "complete gate decision; Chat will not bypass that acceptance surface"
            )
            return "REFUSED", "EXPLICIT_CONTROL_REQUIRED", detail, detail

        detail = (
            "no deterministic explanation binding exists for this wording; ask about "
            "coverage, QA, or a selected element instead"
        )
        return "REFUSED", "QUERY_UNSUPPORTED", detail, detail

    async def _route_revert(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
    ) -> tuple[str, str | None, str | None, tuple[str, ...], str]:
        if conversation.active_candidate_id is None:
            return (
                "REFUSED",
                "NO_ACTIVE_CANDIDATE",
                "undo applies to a candidate; none is active",
                (),
                "no active candidate to undo",
            )
        history = await self._mutations.history(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=conversation.active_candidate_id,
        )
        latest = next(
            (item for item in reversed(history) if item.status == "APPLIED"), None
        )
        if latest is None:
            return (
                "REFUSED",
                "NOTHING_TO_REVERT",
                "the active candidate has no applied mutation to undo",
                (),
                "nothing to undo",
            )
        reverted = await self._mutations.revert(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=conversation.active_candidate_id,
            mutation_id=latest.mutation_id,
        )
        produced = (str(reverted.compensating_mutation.mutation_id),)
        return (
            "ROUTED",
            None,
            None,
            produced,
            f"reverted mutation {latest.sequence}",
        )

    async def _route_design(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
        classification: Classification,
        text: str,
    ) -> tuple[str, str | None, str | None, tuple[str, ...], str]:
        """Design-class intents go to the gateway, which may refuse.

        A refusal here is surfaced verbatim rather than being softened
        into a generic failure: "no certified provider" and "the design
        system moved" call for different actions.
        """
        try:
            outcome = await self._design.request(
                tenant_id=tenant_id,
                project_id=project_id,
                mission_id=conversation.mission_id,
                conversation_id=conversation.conversation_id,
                scope_keys=list(classification.target_keys),
                instruction=text,
            )
        except DdeError as exc:
            return (
                "REFUSED",
                exc.error_code,
                exc.message,
                (),
                exc.message,
            )
        produced = tuple(str(item.artifact_id) for item in outcome.usable)
        await self._link_session(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation.conversation_id,
            session_id=outcome.session.session_id,
        )
        return (
            "ROUTED",
            None,
            None,
            produced,
            f"{len(produced)} direction(s) generated",
        )

    async def _link_session(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        session_id: UUID,
    ) -> None:
        """One conversation, one active design session — not a second chat."""
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                update(frontend_conversations)
                .where(frontend_conversations.c.conversation_id == conversation_id)
                .values(design_session_id=session_id, updated_at=now)
            )
            await uow.commit()

    async def _conversation(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> FrontendConversation:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_conversations).where(
                    frontend_conversations.c.conversation_id == conversation_id,
                    frontend_conversations.c.tenant_id == tenant_id,
                    frontend_conversations.c.project_id == project_id,
                )
            )
            row = result.mappings().first()
        if row is None:
            raise DdeError(
                "POLICY_DENIED",
                "unknown conversation in this project",
                retryable=False,
                details={"conversation_id": str(conversation_id)},
            )
        return FrontendConversation.model_validate(dict(row))

    async def _append(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        role: str,
        text: str,
        classification: Classification,
        outcome: str,
        refusal_code: str | None,
        refusal_detail: str | None,
        produced: tuple[str, ...],
        context_snapshot: dict[str, object],
    ) -> FrontendConversationTurn:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            sequence = (
                int(
                    await uow.connection.scalar(
                        select(
                            func.coalesce(
                                func.max(frontend_conversation_turns.c.sequence), 0
                            )
                        ).where(
                            frontend_conversation_turns.c.conversation_id
                            == conversation_id
                        )
                    )
                    or 0
                )
                + 1
            )
            record = FrontendConversationTurn(
                turn_id=uuid7(),
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation_id,
                sequence=sequence,
                role=role,
                text=text,
                intent=classification.intent.value,
                outcome=outcome,
                refusal_code=refusal_code,
                refusal_detail=refusal_detail,
                resolved_context={
                    "target_keys": list(classification.target_keys),
                    "references": dict(classification.references),
                    "context": context_snapshot,
                },
                produced_refs=list(produced),
                created_at=now,
                updated_at=now,
            )
            await uow.connection.execute(
                frontend_conversation_turns.insert().values(
                    **record.model_dump(exclude={"resolved_context", "produced_refs"}),
                    resolved_context=record.resolved_context,
                    produced_refs=list(produced),
                )
            )
            await uow.commit()
        return record

    async def _context_snapshot(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
    ) -> dict[str, object]:
        """Resolve the authority-owned context that made this turn actionable.

        The client supplies only selection/candidate/screen/viewport identities.
        Contract, PXG, locks, preview and verification state are read back from
        Core here and persisted with the turn, so later evidence never depends
        on a UI assertion about project truth.
        """
        snapshot = await self._reads.snapshot(
            tenant_id=tenant_id, project_id=project_id
        )
        active_locks = await self._locks.active(
            tenant_id=tenant_id, project_id=project_id
        )
        candidate = next(
            (
                card
                for card in snapshot.candidates.cards
                if conversation.active_candidate_id is not None
                and card.candidate_id == str(conversation.active_candidate_id)
            ),
            None,
        )
        return {
            "project_id": str(project_id),
            "mission_id": str(conversation.mission_id)
            if conversation.mission_id
            else None,
            "screen_key": conversation.screen_key,
            "selected_node_keys": list(conversation.selected_node_keys),
            "viewport": conversation.viewport,
            "pxg_revision": snapshot.pxg_revision,
            "contract_version": snapshot.contract_version,
            "coverage": {
                "state": snapshot.coverage.summary_state,
                "stale": snapshot.coverage.stale,
                "availability": snapshot.coverage.availability.value,
            },
            "active_locks": [
                {
                    "lock_id": str(lock.lock_id),
                    "kind": lock.lock_kind,
                    "scope_key": lock.scope_key,
                }
                for lock in active_locks
            ],
            "candidate": (
                {
                    "candidate_id": candidate.candidate_id,
                    "state": candidate.state,
                    "workspace_id": candidate.workspace_id,
                    "preview_session_id": candidate.preview_session_id,
                    "preview_state": candidate.preview_state,
                    "verification_request_state": candidate.verification_request_state,
                    "verification_run_id": candidate.verification_run_id,
                    "verification_run_status": candidate.verification_run_status,
                }
                if candidate
                else None
            ),
        }

    async def latest_for_mission(
        self, *, tenant_id: UUID, project_id: UUID, mission_id: UUID
    ) -> FrontendConversation | None:
        """Return the durable conversation a mission should reopen after reload."""
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(frontend_conversations)
                        .where(
                            frontend_conversations.c.tenant_id == tenant_id,
                            frontend_conversations.c.project_id == project_id,
                            frontend_conversations.c.mission_id == mission_id,
                        )
                        .order_by(frontend_conversations.c.updated_at.desc())
                        .limit(1)
                    )
                )
                .mappings()
                .first()
            )
        return FrontendConversation.model_validate(dict(row)) if row else None

    async def history(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> tuple[FrontendConversationTurn, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                select(frontend_conversation_turns)
                .where(
                    frontend_conversation_turns.c.conversation_id == conversation_id,
                    frontend_conversation_turns.c.tenant_id == tenant_id,
                    frontend_conversation_turns.c.project_id == project_id,
                )
                .order_by(frontend_conversation_turns.c.sequence)
            )
            rows = result.mappings().all()
        return tuple(FrontendConversationTurn.model_validate(dict(row)) for row in rows)
