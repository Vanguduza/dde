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
from engine.studio.mutations.executor import MutationExecutor
from engine.studio.mutations.planner import MutationRequest
from engine.studio.tables import frontend_conversation_turns, frontend_conversations
from engine.truth.db import open_unit_of_work


@dataclass(frozen=True)
class TurnResult:
    """What the composer renders back."""

    turn: FrontendConversationTurn
    classification: Classification
    produced_refs: tuple[str, ...]
    message: str


class FrontendChatService:
    """The shared conversational control plane."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        mutations: MutationExecutor | None = None,
        design: DesignGateway | None = None,
    ) -> None:
        self._engine = engine
        self._mutations = mutations or MutationExecutor(engine)
        self._design = design or DesignGateway(engine)

    async def open(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID | None = None,
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
        if active_candidate_id is not None:
            values["active_candidate_id"] = active_candidate_id
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
            viewport=conversation.viewport,
        )
        classification = classify(text, context)

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
            text=text,
            classification=classification,
            outcome=outcome,
            refusal_code=refusal_code,
            refusal_detail=refusal_detail,
            produced=produced,
        )
        return TurnResult(
            turn=turn,
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
        result = await self._mutations.apply(
            tenant_id=tenant_id,
            project_id=project_id,
            candidate_id=conversation.active_candidate_id,
            requests=requests,
        )
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
        text: str,
        classification: Classification,
        outcome: str,
        refusal_code: str | None,
        refusal_detail: str | None,
        produced: tuple[str, ...],
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
                role="user",
                text=text,
                intent=classification.intent.value,
                outcome=outcome,
                refusal_code=refusal_code,
                refusal_detail=refusal_detail,
                resolved_context={
                    "target_keys": list(classification.target_keys),
                    "references": dict(classification.references),
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
