"""Epistemic annotations for conversational claims."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.ai_claim import AiClaim
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import ai_claims


class ClaimService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.repo = FabricRepository(engine)

    async def annotate(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        turn_id: UUID,
        claim_text: str,
        epistemic_class: str,
        source_refs: list[str],
        confidence: float | None = None,
        verification_state: str = "UNVERIFIED",
    ) -> AiClaim:
        if not claim_text.strip():
            raise DdeError("VALIDATION_FAILED", "claim text is required")
        if confidence is not None and not 0 <= confidence <= 1:
            raise DdeError(
                "VALIDATION_FAILED", "claim confidence must be between 0 and 1"
            )
        if (
            epistemic_class in {"REPOSITORY_FACT", "EXTERNAL_SOURCE"}
            and not source_refs
        ):
            raise DdeError("EVIDENCE_MISSING", "fact/source claim requires source refs")
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "claim_id": uuid7(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "conversation_id": conversation_id,
            "turn_id": turn_id,
            "claim_text": claim_text.strip(),
            "epistemic_class": epistemic_class,
            "confidence": confidence,
            "source_refs": source_refs,
            "verification_state": verification_state,
            "created_at": now,
            "updated_at": now,
        }
        AiClaim.model_validate(values)
        return await self.repo.insert_model(
            table=ai_claims,
            model=AiClaim,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )

    async def list_for_turn(
        self, *, tenant_id: UUID, project_id: UUID, turn_id: UUID
    ) -> tuple[AiClaim, ...]:
        return await self.repo.list_models(
            table=ai_claims,
            model=AiClaim,
            tenant_id=tenant_id,
            project_id=project_id,
            filters={"turn_id": turn_id},
            order_by=(ai_claims.c.created_at.asc(),),
        )
