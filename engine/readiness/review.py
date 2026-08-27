"""Production caller for the Chapter 18.6 removal test and S7 readiness catalog.

`run` evaluates every named §18.6 candidate through `evaluate_candidate`.
Without a supplied counterfactual it fail-closes to KEEP. It appends a
durable `readiness.reviewed` audit event. It never deletes a module.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.audit.service import AuditService
from engine.readiness.inventory import (
    REMOVAL_CANDIDATES,
    S7_PRIOR_LANDINGS,
    missing_inventory_files,
)
from engine.readiness.removal import (
    KEEP,
    RemovalMeasurement,
    RemovalVerdict,
    evaluate_candidate,
)


@dataclass(frozen=True)
class ReadinessResult:
    inventory_complete: bool
    verdicts: tuple[RemovalVerdict, ...]
    proposed_edrs: tuple[str, ...]


class ReadinessReview:
    """Executable §18.6 / S7 production-readiness review."""

    def __init__(
        self,
        engine: AsyncEngine,
        audit: AuditService | None = None,
    ) -> None:
        self._engine = engine
        self._audit = audit or AuditService(engine)

    async def run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        measurements: dict[str, RemovalMeasurement] | None = None,
    ) -> ReadinessResult:
        missing = missing_inventory_files()
        if missing:
            raise RuntimeError(f"readiness inventory missing: {missing}")
        supplied = measurements or {}
        unmeasured = RemovalMeasurement(None, None, None, None)
        verdicts = tuple(
            evaluate_candidate(
                candidate=name,
                measurement=supplied.get(name, unmeasured),
            )
            for name in REMOVAL_CANDIDATES
        )
        proposed = tuple(v.candidate for v in verdicts if v.decision != KEEP)
        await self._audit.append(
            tenant_id=tenant_id,
            project_id=project_id,
            event_type="readiness.reviewed",
            payload={
                "chapter": "18.6",
                "s7_prior_landings": list(S7_PRIOR_LANDINGS),
                "candidates": list(REMOVAL_CANDIDATES),
                "decisions": [v.decision for v in verdicts],
                "proposed_edrs": list(proposed),
            },
        )
        return ReadinessResult(
            inventory_complete=True,
            verdicts=verdicts,
            proposed_edrs=proposed,
        )
