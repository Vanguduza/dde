"""Optional domain context adapters for universal DDE Chat.

The conversation domain is product-neutral. A workspace can contribute richer
context through an adapter without making Chat depend on that workspace for
all turns. Frontend Studio is the first adapter because DDE-069 already has
strong PXG/Contract/Coverage/verification projections.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_conversation import FrontendConversation
from engine.studio.locks.service import LockService
from engine.studio.reads import FrontendReadService


class FrontendStudioChatContextAdapter:
    """Read-only Frontend Studio context contribution for a DDE Chat turn."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        reads: FrontendReadService | None = None,
        locks: LockService | None = None,
    ) -> None:
        self.reads = reads or FrontendReadService(engine)
        self.locks = locks or LockService(engine)

    async def snapshot(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation: FrontendConversation,
    ) -> dict[str, object]:
        snapshot = await self.reads.snapshot(tenant_id=tenant_id, project_id=project_id)
        active_locks = await self.locks.active(
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
