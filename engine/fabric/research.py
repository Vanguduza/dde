"""Cited deep research, provider comparison and council artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.chat.plans import FrontendChatPlanService
from engine.contracts.ai_research_artifact import AiResearchArtifact, ResearchSource
from engine.contracts.frontend_chat_plan import FrontendChatPlan
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import ai_research_artifacts


class ResearchService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.repo = FabricRepository(engine)
        self.plans = FrontendChatPlanService(engine)

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        mode: str,
        question: str,
        scope: dict[str, object] | None = None,
        mission_id: UUID | None = None,
        created_from_turn_id: UUID | None = None,
    ) -> AiResearchArtifact:
        if not question.strip():
            raise DdeError("VALIDATION_FAILED", "research question is required")
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "research_id": uuid7(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "conversation_id": conversation_id,
            "mission_id": mission_id,
            "created_from_turn_id": created_from_turn_id,
            "mode": mode,
            "question": question.strip(),
            "scope": scope or {},
            "state": "DRAFT",
            "source_ledger": [],
            "findings": [],
            "hypotheses": [],
            "unresolved_questions": [],
            "confidence": None,
            "result_refs": [],
            "lock_version": 1,
            "created_at": now,
            "updated_at": now,
        }
        AiResearchArtifact.model_validate(values)
        return await self.repo.insert_model(
            table=ai_research_artifacts,
            model=AiResearchArtifact,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )

    async def add_source(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        research_id: UUID,
        source_kind: str,
        ref: str,
        authority: str,
        lock_version: int,
        title: str | None = None,
        published_at: datetime | None = None,
        content_hash: str | None = None,
        notes: str | None = None,
    ) -> AiResearchArtifact:
        artifact = await self.get(
            tenant_id=tenant_id, project_id=project_id, research_id=research_id
        )
        if artifact.state in {"COMPLETED", "CANCELLED"}:
            raise DdeError(
                "VERSION_CONFLICT", "terminal research artifact cannot accept sources"
            )
        if not ref.strip():
            raise DdeError("VALIDATION_FAILED", "research source ref is required")
        source = ResearchSource(
            source_id=str(uuid7()),
            source_kind=source_kind,
            ref=ref.strip(),
            title=title,
            authority=authority,
            published_at=published_at,
            retrieved_at=datetime.now(UTC),
            content_hash=content_hash,
            notes=notes,
        )
        if any(item.ref == source.ref for item in artifact.source_ledger):
            raise DdeError("VERSION_CONFLICT", "research source already recorded")
        return await self._update(
            artifact,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            source_ledger=[
                *(s.model_dump() for s in artifact.source_ledger),
                source.model_dump(),
            ],
            state="RESEARCHING",
        )

    async def update_analysis(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        research_id: UUID,
        lock_version: int,
        findings: list[dict[str, object]],
        hypotheses: list[dict[str, object]],
        unresolved_questions: list[str],
        result_refs: list[str] | None = None,
    ) -> AiResearchArtifact:
        artifact = await self.get(
            tenant_id=tenant_id, project_id=project_id, research_id=research_id
        )
        if artifact.state in {"COMPLETED", "CANCELLED"}:
            raise DdeError(
                "VERSION_CONFLICT", "terminal research artifact cannot change"
            )
        # Preserve dissent: hypotheses change only through the explicit supplied list;
        # findings never silently collapse them.
        return await self._update(
            artifact,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            findings=findings,
            hypotheses=hypotheses,
            unresolved_questions=unresolved_questions,
            result_refs=result_refs or artifact.result_refs,
            state="SYNTHESIZING",
        )

    async def complete(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        research_id: UUID,
        lock_version: int,
        confidence: float,
        result_refs: list[str],
    ) -> AiResearchArtifact:
        artifact = await self.get(
            tenant_id=tenant_id, project_id=project_id, research_id=research_id
        )
        if not 0 <= confidence <= 1:
            raise DdeError(
                "VALIDATION_FAILED", "research confidence must be between 0 and 1"
            )
        if (
            artifact.mode in {"DEEP_RESEARCH", "COMPARE", "COUNCIL"}
            and not artifact.source_ledger
        ):
            raise DdeError(
                "EVIDENCE_MISSING", "research cannot complete without a source ledger"
            )
        if not artifact.findings and not artifact.hypotheses:
            raise DdeError(
                "EVIDENCE_MISSING",
                "research cannot complete without findings or hypotheses",
            )
        return await self._update(
            artifact,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            state="COMPLETED",
            confidence=confidence,
            result_refs=result_refs,
        )

    async def to_plan(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        research_id: UUID,
        mission_id: UUID,
        selected_finding_indexes: list[int],
        title: str,
    ) -> FrontendChatPlan:
        artifact = await self.get(
            tenant_id=tenant_id, project_id=project_id, research_id=research_id
        )
        if artifact.state != "COMPLETED":
            raise DdeError(
                "VERSION_CONFLICT", "only completed research can become a plan"
            )
        if not selected_finding_indexes:
            raise DdeError("VALIDATION_FAILED", "select at least one finding")
        chosen = []
        for i in selected_finding_indexes:
            if i < 0 or i >= len(artifact.findings):
                raise DdeError(
                    "VALIDATION_FAILED", "finding index is outside research artifact"
                )
            chosen.append(artifact.findings[i])
        # Research converts to a proposal only. There is deliberately no
        # command_type on these steps.
        steps: list[dict[str, object]] = [
            {
                "title": str(item.get("title") or f"Research finding {i + 1}"),
                "description": str(item.get("summary") or item.get("text") or item),
                "parameters": {},
            }
            for i, item in enumerate(chosen)
        ]
        return await self.plans.create(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            conversation_id=artifact.conversation_id,
            title=title,
            objective=artifact.question,
            steps=steps,
            approval_required=True,
            created_from_turn_id=artifact.created_from_turn_id,
            context_snapshot={
                "research_id": str(research_id),
                "source_refs": [s.ref for s in artifact.source_ledger],
            },
        )

    async def get(
        self, *, tenant_id: UUID, project_id: UUID, research_id: UUID
    ) -> AiResearchArtifact:
        return await self.repo.get_model(
            table=ai_research_artifacts,
            model=AiResearchArtifact,
            id_column="research_id",
            object_id=research_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )

    async def list_for_conversation(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> tuple[AiResearchArtifact, ...]:
        return await self.repo.list_models(
            table=ai_research_artifacts,
            model=AiResearchArtifact,
            tenant_id=tenant_id,
            project_id=project_id,
            filters={"conversation_id": conversation_id},
            order_by=(ai_research_artifacts.c.updated_at.desc(),),
        )

    async def _update(
        self,
        artifact: AiResearchArtifact,
        *,
        tenant_id: UUID,
        project_id: UUID,
        lock_version: int,
        **values: object,
    ) -> AiResearchArtifact:
        return await self.repo.update_locked(
            table=ai_research_artifacts,
            model=AiResearchArtifact,
            id_column="research_id",
            object_id=artifact.research_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={**values, "updated_at": datetime.now(UTC)},
        )
