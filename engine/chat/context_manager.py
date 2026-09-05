"""Universal DDE Chat context and token-budget manager.

This is the conversation analogue of DDE Context Intelligence. It protects live
DDE authority, ranks explicit context before semantic memory, replays only the
history a provider actually needs, and persists inspectable compaction lineage.
Provider sessions remain replaceable: a cold provider can rebuild useful state
from this manager without replaying an unbounded transcript.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.chat.context_refs import (
    ContextBudget,
    FrontendChatContextService,
    budget_dict,
)
from engine.chat.tables import frontend_conversation_turns
from engine.contracts.frontend_conversation import FrontendConversation
from engine.fabric.context import ContextSnapshotService
from engine.fabric.memory import MemoryRecallResult, MemoryService
from engine.fabric.policies import DEFAULT_CONTEXT_TOKENS, ConversationPolicyService
from engine.truth.db import open_unit_of_work

SYSTEM_WRAPPER_RESERVE_TOKENS = 320
MIN_EXPLICIT_BUDGET_TOKENS = 1_024
MAX_HISTORY_TURNS = 120
WARM_SESSION_HISTORY_FRACTION = 0.05
COLD_SESSION_HISTORY_FRACTION = 0.20
MEMORY_FRACTION = 0.28
EXPLICIT_FRACTION = 0.52
COMPACTION_SUMMARY_MAX_TOKENS = 1_000


def estimate_tokens(value: object) -> int:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return math.ceil(len(text) / 4) if text else 0


@dataclass(frozen=True)
class HistoryContextItem:
    turn_id: UUID
    sequence: int
    role: str
    intent: str
    outcome: str
    text: str
    estimated_tokens: int


@dataclass(frozen=True)
class ManagedConversationContext:
    budget_tokens: int
    used_tokens: int
    utilization: float
    prompt_tokens: int
    live_context_tokens: int
    system_reserve_tokens: int
    explicit_context: ContextBudget
    memory_context: MemoryRecallResult
    history: tuple[HistoryContextItem, ...]
    history_summary: str | None
    history_summary_tokens: int
    context_snapshot_id: UUID
    compaction_snapshot_id: UUID | None
    omitted_refs: tuple[str, ...]
    omission_reasons: dict[str, str]

    def provider_payload(self) -> dict[str, object]:
        return {
            "allocation": {
                "budget_tokens": self.budget_tokens,
                "used_tokens": self.used_tokens,
                "utilization": self.utilization,
                "prompt_tokens": self.prompt_tokens,
                "live_context_tokens": self.live_context_tokens,
                "system_reserve_tokens": self.system_reserve_tokens,
            },
            "explicit_context": budget_dict(self.explicit_context),
            "memory_context": [asdict(item) for item in self.memory_context.items],
            "history": [asdict(item) for item in self.history],
            "history_summary": self.history_summary,
            "context_snapshot_id": str(self.context_snapshot_id),
            "compaction_snapshot_id": (
                str(self.compaction_snapshot_id)
                if self.compaction_snapshot_id
                else None
            ),
            "omitted_refs": list(self.omitted_refs),
            "omission_reasons": dict(self.omission_reasons),
        }


class DdeConversationContextManager:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        refs: FrontendChatContextService | None = None,
        memory: MemoryService | None = None,
        snapshots: ContextSnapshotService | None = None,
        policies: ConversationPolicyService | None = None,
    ) -> None:
        self.engine = engine
        self.refs = refs or FrontendChatContextService(engine)
        self.memory = memory or MemoryService(engine)
        self.snapshots = snapshots or ContextSnapshotService(engine)
        self.policies = policies or ConversationPolicyService(engine)

    async def assemble_turn(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
        prompt: str,
        live_context: dict[str, object],
        explicit_refs: tuple[str, ...],
    ) -> ManagedConversationContext:
        total_budget = DEFAULT_CONTEXT_TOKENS
        if conversation.policy_id is not None:
            policy = await self.policies.get(
                tenant_id=tenant_id,
                project_id=project_id,
                policy_id=conversation.policy_id,
            )
            total_budget = policy.context_token_budget
        prompt_tokens = estimate_tokens(prompt)
        live_tokens = estimate_tokens(live_context)
        fixed = SYSTEM_WRAPPER_RESERVE_TOKENS + prompt_tokens + live_tokens
        remaining = max(0, total_budget - fixed)

        warm = conversation.active_worker_session_id is not None
        history_fraction = (
            WARM_SESSION_HISTORY_FRACTION if warm else COLD_SESSION_HISTORY_FRACTION
        )
        history_target = int(remaining * history_fraction)
        explicit_target = min(
            remaining,
            max(MIN_EXPLICIT_BUDGET_TOKENS, int(remaining * EXPLICIT_FRACTION)),
        )
        # Memory gets a stable share, plus unused explicit allocation. This prevents
        # a conversation with no @refs from wasting most of its context budget.
        memory_target = int(remaining * MEMORY_FRACTION)
        explicit = await self.refs.assemble(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation.conversation_id,
            refs=explicit_refs,
            budget_tokens=max(1, explicit_target),
        )
        unused_explicit = max(0, explicit_target - explicit.estimated_tokens)
        memory_target += int(unused_explicit * 0.65)
        history_target += unused_explicit - int(unused_explicit * 0.65)

        memory = await self.memory.recall(
            tenant_id=tenant_id,
            project_id=project_id,
            query=prompt,
            scopes=self._memory_scopes(conversation),
            budget_tokens=max(
                0, min(memory_target, remaining - explicit.estimated_tokens)
            ),
        )
        used_before_history = (
            fixed + explicit.estimated_tokens + memory.estimated_tokens
        )
        history_target += max(0, total_budget - used_before_history - history_target)
        history_budget = max(0, min(history_target, total_budget - used_before_history))
        history, history_summary, history_omitted = await self._history(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation.conversation_id,
            budget_tokens=history_budget,
        )
        history_tokens = sum(item.estimated_tokens for item in history)
        summary_tokens = estimate_tokens(history_summary or "")
        used = min(
            total_budget,
            fixed
            + explicit.estimated_tokens
            + memory.estimated_tokens
            + history_tokens
            + summary_tokens,
        )

        omitted: list[str] = list(explicit.omitted_refs)
        reasons = dict(explicit.omission_reasons)
        for memory_id in memory.omitted_memory_ids:
            ref = f"memory:{memory_id}"
            omitted.append(ref)
            reasons[ref] = "MEMORY_RANK_OR_BUDGET_EVICTION"
        for item in history_omitted:
            ref = f"turn:{item.turn_id}"
            omitted.append(ref)
            reasons[ref] = "HISTORY_COMPACTED"

        retained_refs = [
            "live:dde",
            "prompt:current",
            *explicit.included_refs,
            *(f"memory:{item.memory_id}" for item in memory.items),
            *(f"turn:{item.turn_id}" for item in history),
        ]
        if history_summary:
            retained_refs.append("history:compaction_summary")
        manifest = self._manifest(
            explicit=explicit,
            memory=memory,
            history=history,
            live_tokens=live_tokens,
            prompt_tokens=prompt_tokens,
            history_summary_tokens=summary_tokens,
        )
        latest = await self.snapshots.latest(
            tenant_id=tenant_id,
            project_id=project_id,
            conversation_id=conversation.conversation_id,
        )
        predecessor = latest.context_snapshot_id if latest else None
        compaction_id: UUID | None = None
        if history_omitted:
            summary = history_summary or "Older conversation turns were compacted."
            pre = await self.snapshots.create(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation.conversation_id,
                reason="PRE_COMPACTION",
                retained_refs=retained_refs,
                omitted_refs=omitted,
                omission_reasons=reasons,
                item_manifest=manifest,
                estimated_tokens=used,
                budget_tokens=total_budget,
                summary=summary,
                predecessor_snapshot_id=predecessor,
            )
            post = await self.snapshots.create(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation.conversation_id,
                reason="POST_COMPACTION",
                retained_refs=retained_refs,
                omitted_refs=omitted,
                omission_reasons=reasons,
                item_manifest=manifest,
                estimated_tokens=used,
                budget_tokens=total_budget,
                summary=summary,
                predecessor_snapshot_id=pre.context_snapshot_id,
            )
            snapshot = post
            compaction_id = post.context_snapshot_id
        else:
            snapshot = await self.snapshots.create(
                tenant_id=tenant_id,
                project_id=project_id,
                conversation_id=conversation.conversation_id,
                reason="TURN",
                retained_refs=retained_refs,
                omitted_refs=omitted,
                omission_reasons=reasons,
                item_manifest=manifest,
                estimated_tokens=used,
                budget_tokens=total_budget,
                predecessor_snapshot_id=predecessor,
            )
        return ManagedConversationContext(
            budget_tokens=total_budget,
            used_tokens=used,
            utilization=(used / total_budget if total_budget else 1.0),
            prompt_tokens=prompt_tokens,
            live_context_tokens=live_tokens,
            system_reserve_tokens=SYSTEM_WRAPPER_RESERVE_TOKENS,
            explicit_context=explicit,
            memory_context=memory,
            history=history,
            history_summary=history_summary,
            history_summary_tokens=summary_tokens,
            context_snapshot_id=snapshot.context_snapshot_id,
            compaction_snapshot_id=compaction_id,
            omitted_refs=tuple(dict.fromkeys(omitted)),
            omission_reasons=reasons,
        )

    @staticmethod
    def _memory_scopes(conversation: FrontendConversation) -> list[tuple[str, str]]:
        scopes: list[tuple[str, str]] = [
            ("CONVERSATION", str(conversation.conversation_id)),
        ]
        if conversation.mission_id is not None:
            scopes.append(("MISSION", str(conversation.mission_id)))
        scopes.extend(
            [
                ("REPOSITORY", str(conversation.project_id)),
                ("PROJECT", str(conversation.project_id)),
                ("ORGANIZATION", str(conversation.tenant_id)),
            ]
        )
        if conversation.created_by is not None:
            scopes.append(("USER", str(conversation.created_by)))
        return scopes

    async def _history(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        budget_tokens: int,
    ) -> tuple[
        tuple[HistoryContextItem, ...], str | None, tuple[HistoryContextItem, ...]
    ]:
        async with open_unit_of_work(
            self.engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            rows = (
                (
                    await uow.connection.execute(
                        select(frontend_conversation_turns)
                        .where(
                            frontend_conversation_turns.c.conversation_id
                            == conversation_id,
                            frontend_conversation_turns.c.tenant_id == tenant_id,
                            frontend_conversation_turns.c.project_id == project_id,
                        )
                        .order_by(frontend_conversation_turns.c.sequence.asc())
                        .limit(MAX_HISTORY_TURNS)
                    )
                )
                .mappings()
                .all()
            )
        items = tuple(
            HistoryContextItem(
                turn_id=row["turn_id"],
                sequence=int(row["sequence"]),
                role=str(row["role"]),
                intent=str(row["intent"]),
                outcome=str(row["outcome"]),
                text=str(row["text"]),
                estimated_tokens=estimate_tokens(str(row["text"])) + 12,
            )
            for row in rows
        )
        if not items or budget_tokens <= 0:
            return (), None, items
        if sum(item.estimated_tokens for item in items) <= budget_tokens:
            return items, None, ()
        summary_cap = min(
            COMPACTION_SUMMARY_MAX_TOKENS,
            max(128, budget_tokens // 4),
        )
        recent_budget = max(0, budget_tokens - summary_cap)
        selected_rev: list[HistoryContextItem] = []
        used = 0
        for item in reversed(items):
            if used + item.estimated_tokens > recent_budget:
                continue
            selected_rev.append(item)
            used += item.estimated_tokens
        selected = tuple(reversed(selected_rev))
        selected_ids = {item.turn_id for item in selected}
        omitted = tuple(item for item in items if item.turn_id not in selected_ids)
        summary = self._compact_history(omitted, summary_cap)
        # If deterministic summary is smaller than its reserve, use the remaining
        # capacity for additional recent turns before finalizing.
        spare = max(0, summary_cap - estimate_tokens(summary))
        if spare:
            extra_rev: list[HistoryContextItem] = []
            for item in reversed(omitted):
                if item.estimated_tokens <= spare:
                    extra_rev.append(item)
                    spare -= item.estimated_tokens
            if extra_rev:
                extra_ids = {item.turn_id for item in extra_rev}
                selected = tuple(
                    sorted((*selected, *extra_rev), key=lambda item: item.sequence)
                )
                omitted = tuple(
                    item for item in omitted if item.turn_id not in extra_ids
                )
                summary = self._compact_history(omitted, summary_cap)
        return selected, summary, omitted

    @staticmethod
    def _compact_history(items: tuple[HistoryContextItem, ...], max_tokens: int) -> str:
        if not items:
            return ""
        max_chars = max_tokens * 4
        heading = "Compacted earlier DDE Chat history:"
        used = len(heading)
        selected: list[str] = []
        for item in reversed(items[-32:]):
            text = " ".join(item.text.split())
            line = (
                f"- #{item.sequence} {item.role} [{item.intent}/{item.outcome}]: "
                f"{text[:220]}"
            )
            if used + len(line) + 1 > max_chars:
                continue
            selected.append(line)
            used += len(line) + 1
        selected.reverse()
        return "\n".join([heading, *selected])

    @staticmethod
    def _manifest(
        *,
        explicit: ContextBudget,
        memory: MemoryRecallResult,
        history: tuple[HistoryContextItem, ...],
        live_tokens: int,
        prompt_tokens: int,
        history_summary_tokens: int,
    ) -> list[dict[str, object]]:
        result: list[dict[str, object]] = [
            {
                "kind": "LIVE_DDE",
                "ref": "live:dde",
                "tokens": live_tokens,
                "protected": True,
            },
            {
                "kind": "PROMPT",
                "ref": "prompt:current",
                "tokens": prompt_tokens,
                "protected": True,
            },
        ]
        result.extend(
            {
                "kind": f"CONTEXT_{item.kind.upper()}",
                "ref": item.ref,
                "tokens": item.estimated_tokens,
                "source_revision": item.source_revision,
            }
            for item in explicit.items
        )
        result.extend(
            {
                "kind": "MEMORY",
                "ref": f"memory:{item.memory_id}",
                "tokens": item.estimated_tokens,
                "scope": item.scope_kind,
                "trust": item.trust_class,
                "score": item.score,
                "storage_backend": item.storage_backend,
                "truncated": item.truncated,
            }
            for item in memory.items
        )
        result.extend(
            {
                "kind": "HISTORY",
                "ref": f"turn:{item.turn_id}",
                "tokens": item.estimated_tokens,
                "sequence": item.sequence,
            }
            for item in history
        )
        if history_summary_tokens:
            result.append(
                {
                    "kind": "HISTORY_SUMMARY",
                    "ref": "history:compaction_summary",
                    "tokens": history_summary_tokens,
                }
            )
        return result
