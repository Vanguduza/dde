"""DDE-owned execution experience and non-authoritative routing insights."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.experience_record import ExperienceRecord
from engine.contracts.routing_insight_candidate import RoutingInsightCandidate
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import experience_records, routing_insight_candidates

_INSIGHT_TRANSITIONS: dict[str, frozenset[str]] = {
    "CANDIDATE": frozenset({"OFFLINE_REPLAY", "REJECTED", "SUPERSEDED"}),
    "OFFLINE_REPLAY": frozenset({"HOLDOUT", "REJECTED", "SUPERSEDED"}),
    "HOLDOUT": frozenset({"SHADOW", "REJECTED", "SUPERSEDED"}),
    "SHADOW": frozenset({"CANARY", "REJECTED", "SUPERSEDED"}),
    "CANARY": frozenset({"PROMOTED", "REJECTED", "SUPERSEDED"}),
    "PROMOTED": frozenset({"SUPERSEDED"}),
    "REJECTED": frozenset(),
    "SUPERSEDED": frozenset(),
}


class ExperienceService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.repo = FabricRepository(engine)

    async def record(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_signature: dict[str, object],
        worker_configuration: dict[str, object],
        outcome: dict[str, object],
        economics: dict[str, object],
        failure_signatures: list[str],
        verification_refs: list[str],
        authority_refs: list[str],
        mission_id: UUID | None = None,
        task_id: UUID | None = None,
        worker_run_id: UUID | None = None,
        worker_session_id: UUID | None = None,
    ) -> ExperienceRecord:
        if bool(outcome.get("verified")) and not verification_refs:
            raise DdeError(
                "EVIDENCE_MISSING",
                "verified experience requires independent verification refs",
            )
        if not authority_refs:
            raise DdeError(
                "EVIDENCE_MISSING",
                "experience record requires authoritative DDE lineage refs",
            )
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "experience_id": uuid7(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "mission_id": mission_id,
            "task_id": task_id,
            "worker_run_id": worker_run_id,
            "worker_session_id": worker_session_id,
            "task_signature": task_signature,
            "worker_configuration": worker_configuration,
            "outcome": outcome,
            "economics": economics,
            "failure_signatures": failure_signatures,
            "verification_refs": verification_refs,
            "authority_refs": authority_refs,
            "created_at": now,
            "updated_at": now,
        }
        ExperienceRecord.model_validate(values)
        return await self.repo.insert_model(
            table=experience_records,
            model=ExperienceRecord,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )

    async def list_records(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_id: UUID | None = None,
        limit: int = 200,
    ) -> tuple[ExperienceRecord, ...]:
        return await self.repo.list_models(
            table=experience_records,
            model=ExperienceRecord,
            tenant_id=tenant_id,
            project_id=project_id,
            filters={"task_id": task_id} if task_id else None,
            order_by=(experience_records.c.created_at.desc(),),
            limit=limit,
        )

    async def similar(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        task_signature: dict[str, object],
        limit: int = 50,
    ) -> tuple[ExperienceRecord, ...]:
        rows = await self.list_records(
            tenant_id=tenant_id, project_id=project_id, limit=500
        )
        keys = ("domain", "platform", "framework", "operation", "risk_class")
        scored: list[tuple[int, ExperienceRecord]] = []
        for row in rows:
            score = sum(
                1
                for key in keys
                if task_signature.get(key) is not None
                and row.task_signature.get(key) == task_signature.get(key)
            )
            if score:
                scored.append((score, row))
        scored.sort(key=lambda pair: (pair[0], pair[1].created_at), reverse=True)
        return tuple(row for _, row in scored[:limit])

    async def propose_insight(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        source_kind: str,
        source_ref: str,
        proposal: dict[str, object],
        evidence_refs: list[str],
        confidence: float,
    ) -> RoutingInsightCandidate:
        if not 0 <= confidence <= 1:
            raise DdeError(
                "VALIDATION_FAILED", "routing insight confidence must be 0..1"
            )
        if not evidence_refs:
            raise DdeError("EVIDENCE_MISSING", "routing insight requires evidence refs")
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "insight_id": uuid7(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "source_kind": source_kind,
            "source_ref": source_ref,
            "proposal": proposal,
            "evidence_refs": evidence_refs,
            "confidence": confidence,
            "state": "CANDIDATE",
            "evaluation_refs": [],
            "promoted_policy_ref": None,
            "promoted_by": None,
            "promoted_at": None,
            "lock_version": 1,
            "created_at": now,
            "updated_at": now,
        }
        RoutingInsightCandidate.model_validate(values)
        return await self.repo.insert_model(
            table=routing_insight_candidates,
            model=RoutingInsightCandidate,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )

    async def advance_insight(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        insight_id: UUID,
        target: str,
        lock_version: int,
        evaluation_refs: list[str],
        principal_id: UUID | None = None,
        promoted_policy_ref: str | None = None,
    ) -> RoutingInsightCandidate:
        insight = await self.get_insight(
            tenant_id=tenant_id, project_id=project_id, insight_id=insight_id
        )
        if target not in _INSIGHT_TRANSITIONS[insight.state]:
            raise DdeError(
                "VERSION_CONFLICT",
                "illegal routing insight transition",
                details={"from": insight.state, "to": target},
            )
        if target not in {"REJECTED", "SUPERSEDED"} and not evaluation_refs:
            raise DdeError(
                "EVIDENCE_MISSING",
                "routing insight advancement requires evaluation evidence",
            )
        values: dict[str, object] = {
            "state": target,
            "evaluation_refs": evaluation_refs,
            "updated_at": datetime.now(UTC),
        }
        if target == "PROMOTED":
            if principal_id is None or not promoted_policy_ref:
                raise DdeError(
                    "APPROVAL_REQUIRED",
                    "routing insight promotion requires human principal and policy ref",
                )
            values.update(
                promoted_by=principal_id,
                promoted_at=datetime.now(UTC),
                promoted_policy_ref=promoted_policy_ref,
            )
        return await self.repo.update_locked(
            table=routing_insight_candidates,
            model=RoutingInsightCandidate,
            id_column="insight_id",
            object_id=insight_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values=values,
        )

    async def get_insight(
        self, *, tenant_id: UUID, project_id: UUID, insight_id: UUID
    ) -> RoutingInsightCandidate:
        return await self.repo.get_model(
            table=routing_insight_candidates,
            model=RoutingInsightCandidate,
            id_column="insight_id",
            object_id=insight_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )

    async def list_insights(
        self, *, tenant_id: UUID, project_id: UUID, state: str | None = None
    ) -> tuple[RoutingInsightCandidate, ...]:
        return await self.repo.list_models(
            table=routing_insight_candidates,
            model=RoutingInsightCandidate,
            tenant_id=tenant_id,
            project_id=project_id,
            filters={"state": state} if state else None,
            order_by=(routing_insight_candidates.c.updated_at.desc(),),
        )
