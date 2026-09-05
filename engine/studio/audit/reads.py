"""Read projections for DDE-069 Screen Audit.

Current projections deliberately compose non-stale rows across a full audit and
later incremental audits. A stale latest run never masquerades as current
coverage; callers get explicit currentness and UNKNOWN summary state instead.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.screen_audit_evidence import ScreenAuditEvidence
from engine.contracts.screen_audit_finding import ScreenAuditFinding
from engine.contracts.screen_audit_run import ScreenAuditRun
from engine.contracts.screen_audit_screen_record import ScreenAuditScreenRecord
from engine.studio.tables import (
    screen_audit_evidence,
    screen_audit_findings,
    screen_audit_runs,
    screen_audit_screen_records,
)
from engine.truth.db import open_unit_of_work

_TERMINAL_FINDING_STATES = {"RESOLVED", "ACCEPTED_EXCEPTION", "SUPERSEDED"}


@dataclass(frozen=True)
class AuditSummaryProjection:
    availability: str
    currentness: str
    audit_run_id: UUID | None
    run_status: str | None
    trigger: str | None
    summary_state: str
    pxg_revision: int | None
    contract_version: int | None
    source_revision: str | None
    screen_count: int
    unresolved_findings: int
    blocking_findings: int
    stale_findings: int
    finding_counts_by_dimension: dict[str, int]
    assessment_counts: dict[str, int]


@dataclass(frozen=True)
class ScreenMatrixProjection:
    summary: AuditSummaryProjection
    screens: tuple[ScreenAuditScreenRecord, ...]
    findings: tuple[ScreenAuditFinding, ...]


class ScreenAuditReadService:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def latest_run(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> ScreenAuditRun | None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(screen_audit_runs)
                        .where(
                            screen_audit_runs.c.tenant_id == tenant_id,
                            screen_audit_runs.c.project_id == project_id,
                        )
                        .order_by(screen_audit_runs.c.started_at.desc())
                        .limit(1)
                    )
                )
                .mappings()
                .first()
            )
        return ScreenAuditRun.model_validate(dict(row)) if row else None

    async def current_screens(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        pxg_key: str | None = None,
    ) -> tuple[ScreenAuditScreenRecord, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            query = select(screen_audit_screen_records).where(
                screen_audit_screen_records.c.tenant_id == tenant_id,
                screen_audit_screen_records.c.project_id == project_id,
                screen_audit_screen_records.c.stale.is_(False),
            )
            if pxg_key is not None:
                query = query.where(screen_audit_screen_records.c.pxg_key == pxg_key)
            rows = (
                (
                    await uow.connection.execute(
                        query.order_by(
                            screen_audit_screen_records.c.pxg_key,
                            screen_audit_screen_records.c.updated_at.desc(),
                        )
                    )
                )
                .mappings()
                .all()
            )
        seen: set[str] = set()
        result: list[ScreenAuditScreenRecord] = []
        for row in rows:
            key = str(row["pxg_key"])
            if key in seen:
                continue
            seen.add(key)
            result.append(ScreenAuditScreenRecord.model_validate(dict(row)))
        return tuple(result)

    async def current_findings(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        pxg_key: str | None = None,
        include_terminal: bool = False,
    ) -> tuple[ScreenAuditFinding, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            query = select(screen_audit_findings).where(
                screen_audit_findings.c.tenant_id == tenant_id,
                screen_audit_findings.c.project_id == project_id,
                screen_audit_findings.c.stale.is_(False),
            )
            if pxg_key is not None:
                query = query.where(screen_audit_findings.c.pxg_key == pxg_key)
            if not include_terminal:
                query = query.where(
                    screen_audit_findings.c.status.not_in(_TERMINAL_FINDING_STATES)
                )
            rows = (
                (
                    await uow.connection.execute(
                        query.order_by(
                            screen_audit_findings.c.severity,
                            screen_audit_findings.c.dimension,
                            screen_audit_findings.c.first_detected_at,
                        )
                    )
                )
                .mappings()
                .all()
            )
        return tuple(ScreenAuditFinding.model_validate(dict(row)) for row in rows)

    async def finding_by_id(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        finding_id: UUID,
    ) -> ScreenAuditFinding | None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            row = (
                (
                    await uow.connection.execute(
                        select(screen_audit_findings).where(
                            screen_audit_findings.c.finding_id == finding_id,
                            screen_audit_findings.c.tenant_id == tenant_id,
                            screen_audit_findings.c.project_id == project_id,
                        )
                    )
                )
                .mappings()
                .first()
            )
        return ScreenAuditFinding.model_validate(dict(row)) if row else None

    async def evidence_for_finding(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        finding_id: UUID,
    ) -> tuple[ScreenAuditEvidence, ...]:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            finding_row = (
                await uow.connection.execute(
                    select(screen_audit_findings.c.evidence_refs).where(
                        screen_audit_findings.c.finding_id == finding_id,
                        screen_audit_findings.c.tenant_id == tenant_id,
                        screen_audit_findings.c.project_id == project_id,
                    )
                )
            ).first()
            if finding_row is None:
                return ()
            refs = tuple(UUID(str(value)) for value in finding_row[0] or [])
            if not refs:
                return ()
            rows = (
                (
                    await uow.connection.execute(
                        select(screen_audit_evidence)
                        .where(
                            screen_audit_evidence.c.tenant_id == tenant_id,
                            screen_audit_evidence.c.project_id == project_id,
                            screen_audit_evidence.c.evidence_id.in_(refs),
                        )
                        .order_by(screen_audit_evidence.c.observed_at)
                    )
                )
                .mappings()
                .all()
            )
        return tuple(ScreenAuditEvidence.model_validate(dict(row)) for row in rows)

    async def summary(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> AuditSummaryProjection:
        latest = await self.latest_run(tenant_id=tenant_id, project_id=project_id)
        if latest is None:
            return AuditSummaryProjection(
                availability="NOT_EVALUATED",
                currentness="UNKNOWN",
                audit_run_id=None,
                run_status=None,
                trigger=None,
                summary_state="UNKNOWN",
                pxg_revision=None,
                contract_version=None,
                source_revision=None,
                screen_count=0,
                unresolved_findings=0,
                blocking_findings=0,
                stale_findings=0,
                finding_counts_by_dimension={},
                assessment_counts={},
            )
        screens = await self.current_screens(tenant_id=tenant_id, project_id=project_id)
        findings = await self.current_findings(
            tenant_id=tenant_id, project_id=project_id
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            stale_rows = (
                await uow.connection.execute(
                    select(screen_audit_findings.c.finding_id).where(
                        screen_audit_findings.c.tenant_id == tenant_id,
                        screen_audit_findings.c.project_id == project_id,
                        screen_audit_findings.c.stale.is_(True),
                    )
                )
            ).all()
        by_dimension = Counter(item.dimension for item in findings)
        assessments = Counter(item.assessment_state for item in screens)
        blocking = sum(1 for item in findings if item.severity == "BLOCKING")
        currentness = "STALE" if latest.stale else "CURRENT"
        summary_state = "UNKNOWN" if latest.stale else latest.summary_state
        return AuditSummaryProjection(
            availability="AVAILABLE",
            currentness=currentness,
            audit_run_id=latest.audit_run_id,
            run_status=latest.status,
            trigger=latest.trigger,
            summary_state=summary_state,
            pxg_revision=latest.pxg_revision,
            contract_version=latest.frontend_contract_version,
            source_revision=latest.source_revision,
            screen_count=len(screens),
            unresolved_findings=len(findings),
            blocking_findings=blocking,
            stale_findings=len(stale_rows),
            finding_counts_by_dimension=dict(sorted(by_dimension.items())),
            assessment_counts=dict(sorted(assessments.items())),
        )

    async def matrix(
        self, *, tenant_id: UUID, project_id: UUID
    ) -> ScreenMatrixProjection:
        summary = await self.summary(tenant_id=tenant_id, project_id=project_id)
        screens = await self.current_screens(tenant_id=tenant_id, project_id=project_id)
        findings = await self.current_findings(
            tenant_id=tenant_id, project_id=project_id
        )
        return ScreenMatrixProjection(
            summary=summary, screens=screens, findings=findings
        )
