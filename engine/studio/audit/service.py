"""DDE-069 Screen Audit execution, persistence and invalidation.

Screen Audit derives from PXG, Frontend Contract, Coverage rules and accepted
verification evidence. It never writes those upstream truths. Audit rows are
version-pinned observations whose stale state is explicit and whose findings
remain durable after later recomputation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.frontend_contract import FrontendContract
from engine.contracts.screen_audit_evidence import ScreenAuditEvidence
from engine.contracts.screen_audit_finding import ScreenAuditFinding
from engine.contracts.screen_audit_resolution import ScreenAuditResolution
from engine.contracts.screen_audit_run import ScreenAuditRun
from engine.contracts.screen_audit_screen_record import ScreenAuditScreenRecord
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.audit.rules import (
    POLICY_VERSION,
    AuditComputation,
    AuditEvidenceDraft,
    AuditFindingDraft,
    reconcile,
)
from engine.studio.contract.service import FrontendContractService
from engine.studio.pxg.service import PxgGraph, PxgService
from engine.studio.tables import (
    frontend_candidates,
    screen_audit_evidence,
    screen_audit_findings,
    screen_audit_resolutions,
    screen_audit_runs,
    screen_audit_screen_records,
)
from engine.truth.db import open_unit_of_work
from engine.verification.tables import acceptance_oracles, verification_runs

_UNRESOLVED_FINDING_STATES = {
    "DETECTED",
    "CONFIRMED",
    "CANDIDATE_CREATED",
    "ASSIGNED",
    "VERIFYING",
    "BLOCKED",
}


@dataclass(frozen=True)
class AcceptedVerification:
    pxg_key: str
    verification_run_id: UUID
    kinds: frozenset[str]
    confidence: float
    evidence_refs: tuple[UUID, ...]
    subject_kind: str


@dataclass(frozen=True)
class AuditExecution:
    run: ScreenAuditRun
    screen_count: int
    finding_count: int
    evidence_count: int


def _uuid_value(value: object) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


def _str_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


class ScreenAuditService:
    """Sole writer for the Screen Audit domain."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        pxg: PxgService | None = None,
        contracts: FrontendContractService | None = None,
    ) -> None:
        self._engine = engine
        self._pxg = pxg or PxgService(engine)
        self._contracts = contracts or FrontendContractService(engine)

    async def run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID | None,
        trigger: str = "MANUAL",
        affected_keys: tuple[str, ...] = (),
        source_revision: str | None = None,
        role_policy_hash: str | None = None,
        design_system_hash: str | None = None,
        parent_audit_run_id: UUID | None = None,
    ) -> AuditExecution:
        if trigger not in {
            "FULL",
            "INCREMENTAL",
            "MANUAL",
            "CONTRACT_CHANGE",
            "PXG_CHANGE",
            "PROMOTION",
            "VERIFICATION_CHANGE",
            "SOURCE_CHANGE",
        }:
            raise DdeError("VALIDATION_FAILED", "unknown Screen Audit trigger")
        if trigger == "INCREMENTAL" and not affected_keys:
            raise DdeError(
                "VALIDATION_FAILED",
                "incremental Screen Audit requires affected PXG keys",
            )

        graph = await self._pxg.load(tenant_id=tenant_id, project_id=project_id)
        affected_keys = self._expand_affected_keys(graph, affected_keys)
        contract = await self._contracts.get_active(
            tenant_id=tenant_id, project_id=project_id
        )
        if source_revision is None:
            source_revision = self._derive_source_revision(graph)
        if parent_audit_run_id is None:
            parent = await self.latest_run(
                tenant_id=tenant_id, project_id=project_id, include_stale=True
            )
            parent_audit_run_id = parent.audit_run_id if parent else None

        started = await self._create_running_run(
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            graph=graph,
            contract=contract,
            trigger=trigger,
            affected_keys=affected_keys,
            source_revision=source_revision,
            role_policy_hash=role_policy_hash,
            design_system_hash=design_system_hash,
            parent_audit_run_id=parent_audit_run_id,
        )
        try:
            accepted = await self._accepted_verifications(
                tenant_id=tenant_id, project_id=project_id, graph=graph
            )
            computation = reconcile(
                contract,
                graph,
                passing_verifications={item.pxg_key: item.kinds for item in accepted},
                affected_keys=frozenset(affected_keys) if affected_keys else None,
            )
            computation = self._with_runtime_evidence(
                computation,
                accepted=accepted,
                source_revision=source_revision,
            )
            await self._ensure_inputs_current(
                tenant_id=tenant_id,
                project_id=project_id,
                graph=graph,
                contract=contract,
                audit_run_id=started.audit_run_id,
            )
            await self._invalidate_prior(
                tenant_id=tenant_id,
                project_id=project_id,
                current_run_id=started.audit_run_id,
                affected_keys=affected_keys,
            )
            run = await self._persist_computation(started, computation)
            return AuditExecution(
                run=run,
                screen_count=len(computation.screens),
                finding_count=len(computation.findings),
                evidence_count=len(computation.evidence),
            )
        except Exception:
            await self._mark_failed(
                tenant_id=tenant_id,
                project_id=project_id,
                audit_run_id=started.audit_run_id,
            )
            raise

    async def invalidate_all(self, *, tenant_id: UUID, project_id: UUID) -> int:
        """Mark every current audit observation stale after a project-wide
        input change."""
        now = datetime.now(UTC)
        changed = 0
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            for table in (
                screen_audit_screen_records,
                screen_audit_evidence,
                screen_audit_findings,
                screen_audit_runs,
            ):
                result = await uow.connection.execute(
                    update(table)
                    .where(
                        table.c.tenant_id == tenant_id,
                        table.c.project_id == project_id,
                        table.c.stale.is_(False),
                    )
                    .values(stale=True, updated_at=now)
                )
                changed += int(result.rowcount or 0)
            await uow.commit()
        return changed

    async def invalidate_affected(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        affected_keys: tuple[str, ...],
    ) -> int:
        """Invalidate only audit evidence whose dependency can be affected."""
        graph = await self._pxg.load(tenant_id=tenant_id, project_id=project_id)
        clean = self._expand_affected_keys(graph, affected_keys)
        if not clean:
            return 0
        now = datetime.now(UTC)
        finding_conditions = [
            or_(
                screen_audit_findings.c.pxg_key == key,
                screen_audit_findings.c.node_key == key,
                screen_audit_findings.c.dependency_keys.contains([key]),
            )
            for key in clean
        ]
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            result = await uow.connection.execute(
                update(screen_audit_screen_records)
                .where(
                    screen_audit_screen_records.c.tenant_id == tenant_id,
                    screen_audit_screen_records.c.project_id == project_id,
                    screen_audit_screen_records.c.pxg_key.in_(clean),
                    screen_audit_screen_records.c.stale.is_(False),
                )
                .values(stale=True, updated_at=now)
            )
            await uow.connection.execute(
                update(screen_audit_evidence)
                .where(
                    screen_audit_evidence.c.tenant_id == tenant_id,
                    screen_audit_evidence.c.project_id == project_id,
                    screen_audit_evidence.c.pxg_key.in_(clean),
                    screen_audit_evidence.c.stale.is_(False),
                )
                .values(stale=True, updated_at=now)
            )
            if finding_conditions:
                await uow.connection.execute(
                    update(screen_audit_findings)
                    .where(
                        screen_audit_findings.c.tenant_id == tenant_id,
                        screen_audit_findings.c.project_id == project_id,
                        screen_audit_findings.c.stale.is_(False),
                        or_(*finding_conditions),
                    )
                    .values(stale=True, updated_at=now)
                )
            await uow.connection.execute(
                update(screen_audit_runs)
                .where(
                    screen_audit_runs.c.tenant_id == tenant_id,
                    screen_audit_runs.c.project_id == project_id,
                    screen_audit_runs.c.stale.is_(False),
                )
                .values(stale=True, updated_at=now)
            )
            await uow.commit()
        return int(result.rowcount or 0)

    async def accept_exception(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        finding_id: UUID,
        decision_ref: str,
        principal_id: UUID | None,
    ) -> ScreenAuditFinding:
        clean_decision = decision_ref.strip()
        if not clean_decision:
            raise DdeError(
                "EVIDENCE_MISSING",
                "accepted Screen Audit exception requires a durable decision ref",
            )
        now = datetime.now(UTC)
        resolution_id = uuid7()
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
            if row is None:
                raise DdeError("NOT_FOUND", "Screen Audit finding not found")
            current = ScreenAuditFinding.model_validate(dict(row))
            if current.stale or current.status not in _UNRESOLVED_FINDING_STATES:
                raise DdeError(
                    "VERSION_CONFLICT",
                    "only a current unresolved finding can accept an exception",
                )
            resolution = ScreenAuditResolution(
                resolution_id=resolution_id,
                finding_id=finding_id,
                tenant_id=tenant_id,
                project_id=project_id,
                resolution_kind="ACCEPTED_EXCEPTION",
                candidate_id=None,
                accepted_revision=None,
                decision_ref=clean_decision,
                evidence_refs=current.evidence_refs,
                resolved_by=principal_id,
                resolved_at=now,
                created_at=now,
                updated_at=now,
            )
            values = resolution.model_dump()
            values["evidence_refs"] = [str(ref) for ref in resolution.evidence_refs]
            await uow.connection.execute(
                screen_audit_resolutions.insert().values(**values)
            )
            updated = (
                (
                    await uow.connection.execute(
                        update(screen_audit_findings)
                        .where(
                            screen_audit_findings.c.finding_id == finding_id,
                            screen_audit_findings.c.lock_version
                            == current.lock_version,
                        )
                        .values(
                            status="ACCEPTED_EXCEPTION",
                            decision_ref=clean_decision,
                            resolved_at=now,
                            resolution_ref=resolution_id,
                            lock_version=current.lock_version + 1,
                            updated_at=now,
                        )
                        .returning(screen_audit_findings)
                    )
                )
                .mappings()
                .first()
            )
            if updated is None:
                raise DdeError("VERSION_CONFLICT", "Screen Audit finding changed")
            await uow.commit()
        return ScreenAuditFinding.model_validate(dict(updated))

    async def latest_run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        include_stale: bool = False,
    ) -> ScreenAuditRun | None:
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            query = select(screen_audit_runs).where(
                screen_audit_runs.c.tenant_id == tenant_id,
                screen_audit_runs.c.project_id == project_id,
            )
            if not include_stale:
                query = query.where(screen_audit_runs.c.stale.is_(False))
            row = (
                (
                    await uow.connection.execute(
                        query.order_by(screen_audit_runs.c.started_at.desc()).limit(1)
                    )
                )
                .mappings()
                .first()
            )
        return ScreenAuditRun.model_validate(dict(row)) if row else None

    async def _create_running_run(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        mission_id: UUID | None,
        graph: PxgGraph,
        contract: FrontendContract | None,
        trigger: str,
        affected_keys: tuple[str, ...],
        source_revision: str | None,
        role_policy_hash: str | None,
        design_system_hash: str | None,
        parent_audit_run_id: UUID | None,
    ) -> ScreenAuditRun:
        now = datetime.now(UTC)
        record = ScreenAuditRun(
            audit_run_id=uuid7(),
            tenant_id=tenant_id,
            project_id=project_id,
            mission_id=mission_id,
            source_revision=source_revision,
            pxg_revision=graph.revision,
            frontend_contract_id=contract.contract_id if contract else None,
            frontend_contract_version=contract.contract_version if contract else None,
            policy_version=POLICY_VERSION,
            role_policy_hash=role_policy_hash,
            design_system_hash=design_system_hash,
            started_at=now,
            completed_at=None,
            status="RUNNING",
            trigger=trigger,
            parent_audit_run_id=parent_audit_run_id,
            summary_state="UNKNOWN",
            affected_keys=list(affected_keys),
            stale=False,
            lock_version=1,
            created_at=now,
            updated_at=now,
        )
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                screen_audit_runs.insert().values(**record.model_dump())
            )
            await uow.commit()
        return record

    async def _ensure_inputs_current(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        graph: PxgGraph,
        contract: FrontendContract | None,
        audit_run_id: UUID,
    ) -> None:
        current_revision = await self._pxg.current_revision(
            tenant_id=tenant_id, project_id=project_id
        )
        current_contract = await self._contracts.get_active(
            tenant_id=tenant_id, project_id=project_id
        )
        same_contract = (contract is None and current_contract is None) or (
            contract is not None
            and current_contract is not None
            and contract.contract_id == current_contract.contract_id
            and contract.contract_version == current_contract.contract_version
        )
        if current_revision == graph.revision and same_contract:
            return
        await self._mark_terminal(
            tenant_id=tenant_id,
            project_id=project_id,
            audit_run_id=audit_run_id,
            status="SUPERSEDED",
            summary_state="UNKNOWN",
        )
        raise DdeError(
            "VERSION_CONFLICT",
            "Screen Audit inputs changed while the run was evaluating",
            retryable=True,
        )

    async def _persist_computation(
        self, run: ScreenAuditRun, computation: AuditComputation
    ) -> ScreenAuditRun:
        now = datetime.now(UTC)
        evidence_models: list[ScreenAuditEvidence] = []
        evidence_ids: dict[str, UUID] = {}
        for evidence_draft in computation.evidence:
            evidence_id = uuid7()
            evidence_ids[evidence_draft.key] = evidence_id
            evidence_models.append(
                ScreenAuditEvidence(
                    evidence_id=evidence_id,
                    audit_run_id=run.audit_run_id,
                    finding_id=None,
                    tenant_id=run.tenant_id,
                    project_id=run.project_id,
                    pxg_key=evidence_draft.pxg_key,
                    dimension=evidence_draft.dimension,
                    evidence_kind=evidence_draft.evidence_kind,
                    source_type=evidence_draft.source_type,
                    source_ref=evidence_draft.source_ref,
                    source_revision=evidence_draft.source_revision,
                    content_hash=evidence_draft.content_hash,
                    assessment_state=evidence_draft.assessment_state,
                    metadata=evidence_draft.metadata,
                    stale=False,
                    observed_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )

        finding_models: list[ScreenAuditFinding] = []
        for finding_draft in computation.findings:
            missing = sorted(set(finding_draft.evidence_keys) - set(evidence_ids))
            if missing:
                raise DdeError(
                    "EVIDENCE_MISSING",
                    "Screen Audit finding references unresolved evidence",
                    details={
                        "evidence_keys": missing,
                        "rule_id": finding_draft.rule_id,
                    },
                )
            refs = [evidence_ids[key] for key in finding_draft.evidence_keys]
            finding_models.append(
                ScreenAuditFinding(
                    finding_id=uuid7(),
                    audit_run_id=run.audit_run_id,
                    tenant_id=run.tenant_id,
                    project_id=run.project_id,
                    pxg_key=finding_draft.pxg_key,
                    node_key=finding_draft.node_key,
                    finding_type=finding_draft.finding_type,
                    dimension=finding_draft.dimension,
                    severity=finding_draft.severity,
                    status="DETECTED",
                    assessment_state=finding_draft.assessment_state,
                    message=finding_draft.message,
                    evidence_refs=refs,
                    requirement_refs=list(finding_draft.requirement_refs),
                    journey_refs=list(finding_draft.journey_refs),
                    role_refs=list(finding_draft.role_refs),
                    dependency_keys=list(finding_draft.dependency_keys),
                    rule_id=finding_draft.rule_id,
                    rule_version=POLICY_VERSION,
                    first_detected_at=now,
                    last_observed_at=now,
                    resolved_at=None,
                    resolution_ref=None,
                    decision_ref=finding_draft.decision_ref,
                    stale=False,
                    lock_version=1,
                    created_at=now,
                    updated_at=now,
                )
            )

        screen_models = [
            ScreenAuditScreenRecord(
                record_id=uuid7(),
                audit_run_id=run.audit_run_id,
                tenant_id=run.tenant_id,
                project_id=run.project_id,
                pxg_key=screen_draft.pxg_key,
                screen_kind=screen_draft.screen_kind,
                platform=screen_draft.platform,
                module_or_product_area=screen_draft.module_or_product_area,
                route_identity=screen_draft.route_identity,
                source_refs=list(screen_draft.source_refs),
                journey_refs=list(screen_draft.journey_refs),
                role_refs=list(screen_draft.role_refs),
                feature_requirement_refs=list(screen_draft.feature_requirement_refs),
                data_dependency_refs=list(screen_draft.data_dependency_refs),
                component_inventory_ref=None,
                verification_binding_refs=list(screen_draft.verification_binding_refs),
                render_evidence_refs=list(screen_draft.render_evidence_refs),
                implementation_state=screen_draft.implementation_state,
                assessment_state=screen_draft.assessment_state,
                dimension_states=screen_draft.dimension_states,
                stale=False,
                created_at=now,
                updated_at=now,
            )
            for screen_draft in computation.screens
        ]
        status = "BLOCKED" if computation.summary_state == "BLOCKED" else "COMPLETED"
        async with open_unit_of_work(
            self._engine, tenant_id=run.tenant_id, project_id=run.project_id
        ) as uow:
            for screen_model in screen_models:
                await uow.connection.execute(
                    screen_audit_screen_records.insert().values(
                        **screen_model.model_dump()
                    )
                )
            for evidence_model in evidence_models:
                await uow.connection.execute(
                    screen_audit_evidence.insert().values(**evidence_model.model_dump())
                )
            for finding_model in finding_models:
                values = finding_model.model_dump()
                values["evidence_refs"] = [
                    str(ref) for ref in finding_model.evidence_refs
                ]
                await uow.connection.execute(
                    screen_audit_findings.insert().values(**values)
                )
            updated = (
                (
                    await uow.connection.execute(
                        update(screen_audit_runs)
                        .where(
                            screen_audit_runs.c.audit_run_id == run.audit_run_id,
                            screen_audit_runs.c.status == "RUNNING",
                        )
                        .values(
                            status=status,
                            summary_state=computation.summary_state,
                            completed_at=now,
                            lock_version=run.lock_version + 1,
                            updated_at=now,
                        )
                        .returning(screen_audit_runs)
                    )
                )
                .mappings()
                .first()
            )
            if updated is None:
                raise DdeError("VERSION_CONFLICT", "Screen Audit run changed")
            await uow.commit()
        return ScreenAuditRun.model_validate(dict(updated))

    async def _accepted_verifications(
        self, *, tenant_id: UUID, project_id: UUID, graph: PxgGraph
    ) -> tuple[AcceptedVerification, ...]:
        descriptors: dict[tuple[UUID, str], list[str]] = {}
        for node in graph.nodes_of_kind("screen"):
            task_id = _uuid_value(node.provenance.get("authored_by_task_id"))
            oracle_version = node.attributes.get("acceptance_oracle_version")
            if task_id is None or not isinstance(oracle_version, str):
                continue
            descriptors.setdefault((task_id, oracle_version), []).append(node.pxg_key)
        if not descriptors:
            return ()

        task_ids = tuple({key[0] for key in descriptors})
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            oracle_rows = (
                (
                    await uow.connection.execute(
                        select(acceptance_oracles).where(
                            acceptance_oracles.c.tenant_id == tenant_id,
                            acceptance_oracles.c.project_id == project_id,
                            acceptance_oracles.c.task_id.in_(task_ids),
                        )
                    )
                )
                .mappings()
                .all()
            )
            oracle_by_descriptor = {
                (row["task_id"], row["oracle_version"]): row["oracle_id"]
                for row in oracle_rows
                if row["task_id"] is not None
            }
            oracle_ids = tuple(set(oracle_by_descriptor.values()))
            if not oracle_ids:
                return ()
            run_rows = (
                (
                    await uow.connection.execute(
                        select(verification_runs)
                        .where(
                            verification_runs.c.tenant_id == tenant_id,
                            verification_runs.c.project_id == project_id,
                            verification_runs.c.oracle_id.in_(oracle_ids),
                        )
                        .order_by(
                            verification_runs.c.oracle_id,
                            verification_runs.c.sequence.desc(),
                        )
                    )
                )
                .mappings()
                .all()
            )
            candidate_ids = tuple(
                {
                    row["subject_id"]
                    for row in run_rows
                    if row["subject_kind"] == "FRONTEND_CANDIDATE"
                    and row["subject_id"] is not None
                }
            )
            candidate_rows: Sequence[RowMapping] = ()
            if candidate_ids:
                candidate_rows = (
                    (
                        await uow.connection.execute(
                            select(frontend_candidates).where(
                                frontend_candidates.c.tenant_id == tenant_id,
                                frontend_candidates.c.project_id == project_id,
                                frontend_candidates.c.candidate_id.in_(candidate_ids),
                            )
                        )
                    )
                    .mappings()
                    .all()
                )
        candidate_by_id = {row["candidate_id"]: row for row in candidate_rows}
        current_by_oracle: dict[UUID, RowMapping] = {}
        for row in run_rows:
            oracle_id = row["oracle_id"]
            if oracle_id in current_by_oracle:
                continue
            subject_kind = row["subject_kind"]
            accepted = subject_kind == "WORKER_RUN" or (
                subject_kind is None and row["worker_run_id"] is not None
            )
            if subject_kind == "FRONTEND_CANDIDATE" and row["subject_id"] is not None:
                candidate = candidate_by_id.get(row["subject_id"])
                accepted = bool(
                    candidate
                    and candidate["state"] == "PROMOTED"
                    and candidate["verification_run_id"] == row["verification_run_id"]
                )
            if accepted:
                current_by_oracle[oracle_id] = row

        result: list[AcceptedVerification] = []
        for descriptor, screen_keys in descriptors.items():
            oracle_id = oracle_by_descriptor.get(descriptor)
            if oracle_id is None:
                continue
            current_row = current_by_oracle.get(oracle_id)
            if current_row is None:
                continue
            if current_row["status"] != "PASSED":
                continue
            check_results = (
                row["check_results"] if isinstance(row["check_results"], list) else []
            )
            kinds = frozenset(
                str(item.get("kind"))
                for item in check_results
                if isinstance(item, dict)
                and item.get("status") == "PASSED"
                and isinstance(item.get("kind"), str)
            )
            refs = tuple(
                ref
                for ref in (
                    _uuid_value(value) for value in (current_row["evidence_refs"] or [])
                )
                if ref is not None
            )
            for screen_key in screen_keys:
                result.append(
                    AcceptedVerification(
                        pxg_key=screen_key,
                        verification_run_id=current_row["verification_run_id"],
                        kinds=kinds,
                        confidence=float(current_row["confidence"]),
                        evidence_refs=refs,
                        subject_kind=str(current_row["subject_kind"] or "WORKER_RUN"),
                    )
                )
        return tuple(result)

    @staticmethod
    def _with_runtime_evidence(
        computation: AuditComputation,
        *,
        accepted: tuple[AcceptedVerification, ...],
        source_revision: str | None,
    ) -> AuditComputation:
        evidence = list(computation.evidence)
        findings = list(computation.findings)
        for item in accepted:
            evidence.append(
                AuditEvidenceDraft(
                    key=f"verification:{item.verification_run_id}:{item.pxg_key}",
                    dimension="VERIFICATION",
                    evidence_kind="VERIFICATION_RUN",
                    source_type="VerificationRun",
                    source_ref=str(item.verification_run_id),
                    pxg_key=item.pxg_key,
                    source_revision=source_revision,
                    assessment_state="PASS",
                    metadata={
                        "kinds": sorted(item.kinds),
                        "confidence": item.confidence,
                        "evidence_refs": [str(ref) for ref in item.evidence_refs],
                        "subject_kind": item.subject_kind,
                    },
                )
            )
        summary = computation.summary_state
        if source_revision is None:
            evidence.append(
                AuditEvidenceDraft(
                    key="source:revision:unknown",
                    dimension="SOURCE_PROVENANCE",
                    evidence_kind="SOURCE_REVISION",
                    source_type="ProjectSource",
                    source_ref="UNAVAILABLE",
                    assessment_state="UNKNOWN",
                    metadata={},
                )
            )
            findings.append(
                AuditFindingDraft(
                    finding_type="SOURCE_REVISION_UNKNOWN",
                    dimension="SOURCE_PROVENANCE",
                    severity="WARNING",
                    assessment_state="UNKNOWN",
                    message=(
                        "Accepted source revision is unavailable; audit remains "
                        "inspectable but cannot claim full source reproducibility."
                    ),
                    rule_id="source.revision_known",
                    evidence_keys=("source:revision:unknown",),
                    dependency_keys=("source:revision",),
                )
            )
            if summary == "PASS":
                summary = "PARTIAL"
        return AuditComputation(
            screens=computation.screens,
            findings=tuple(findings),
            evidence=tuple(evidence),
            summary_state=summary,
        )

    async def _invalidate_prior(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        current_run_id: UUID,
        affected_keys: tuple[str, ...],
    ) -> None:
        now = datetime.now(UTC)
        clean = tuple(dict.fromkeys(key for key in affected_keys if key.strip()))
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                update(screen_audit_runs)
                .where(
                    screen_audit_runs.c.tenant_id == tenant_id,
                    screen_audit_runs.c.project_id == project_id,
                    screen_audit_runs.c.audit_run_id != current_run_id,
                    screen_audit_runs.c.stale.is_(False),
                )
                .values(stale=True, updated_at=now)
            )
            child_tables = (
                screen_audit_screen_records,
                screen_audit_evidence,
                screen_audit_findings,
            )
            if not clean:
                for table in child_tables:
                    await uow.connection.execute(
                        update(table)
                        .where(
                            table.c.tenant_id == tenant_id,
                            table.c.project_id == project_id,
                            table.c.audit_run_id != current_run_id,
                            table.c.stale.is_(False),
                        )
                        .values(stale=True, updated_at=now)
                    )
            else:
                await uow.connection.execute(
                    update(screen_audit_screen_records)
                    .where(
                        screen_audit_screen_records.c.tenant_id == tenant_id,
                        screen_audit_screen_records.c.project_id == project_id,
                        screen_audit_screen_records.c.audit_run_id != current_run_id,
                        screen_audit_screen_records.c.pxg_key.in_(clean),
                        screen_audit_screen_records.c.stale.is_(False),
                    )
                    .values(stale=True, updated_at=now)
                )
                await uow.connection.execute(
                    update(screen_audit_evidence)
                    .where(
                        screen_audit_evidence.c.tenant_id == tenant_id,
                        screen_audit_evidence.c.project_id == project_id,
                        screen_audit_evidence.c.audit_run_id != current_run_id,
                        screen_audit_evidence.c.pxg_key.in_(clean),
                        screen_audit_evidence.c.stale.is_(False),
                    )
                    .values(stale=True, updated_at=now)
                )
                finding_conditions = [
                    or_(
                        screen_audit_findings.c.pxg_key == key,
                        screen_audit_findings.c.node_key == key,
                        screen_audit_findings.c.dependency_keys.contains([key]),
                    )
                    for key in clean
                ]
                await uow.connection.execute(
                    update(screen_audit_findings)
                    .where(
                        screen_audit_findings.c.tenant_id == tenant_id,
                        screen_audit_findings.c.project_id == project_id,
                        screen_audit_findings.c.audit_run_id != current_run_id,
                        screen_audit_findings.c.stale.is_(False),
                        or_(*finding_conditions),
                    )
                    .values(stale=True, updated_at=now)
                )
            await uow.commit()

    async def _mark_failed(
        self, *, tenant_id: UUID, project_id: UUID, audit_run_id: UUID
    ) -> None:
        await self._mark_terminal(
            tenant_id=tenant_id,
            project_id=project_id,
            audit_run_id=audit_run_id,
            status="FAILED",
            summary_state="UNKNOWN",
        )

    async def _mark_terminal(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        audit_run_id: UUID,
        status: str,
        summary_state: str,
    ) -> None:
        now = datetime.now(UTC)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as uow:
            await uow.connection.execute(
                update(screen_audit_runs)
                .where(
                    screen_audit_runs.c.audit_run_id == audit_run_id,
                    screen_audit_runs.c.status == "RUNNING",
                )
                .values(
                    status=status,
                    summary_state=summary_state,
                    completed_at=now,
                    lock_version=screen_audit_runs.c.lock_version + 1,
                    updated_at=now,
                )
            )
            await uow.commit()

    @staticmethod
    def _expand_affected_keys(
        graph: PxgGraph, affected_keys: tuple[str, ...]
    ) -> tuple[str, ...]:
        """Include stable screen ancestry for dependency-directed invalidation."""
        expanded: list[str] = []
        screen_keys = {node.pxg_key for node in graph.nodes_of_kind("screen")}
        for raw in affected_keys:
            key = raw.strip()
            if not key:
                continue
            expanded.append(key)
            node = graph.node_by_key(key)
            seen: set[str] = set()
            while node is not None and node.pxg_key not in seen:
                seen.add(node.pxg_key)
                if node.node_kind == "screen":
                    expanded.append(node.pxg_key)
                    break
                node = graph.node_by_key(node.parent_key) if node.parent_key else None
            else:
                prefixes = [
                    screen
                    for screen in screen_keys
                    if key.startswith(screen + "#") or key.startswith(screen + "/")
                ]
                if prefixes:
                    expanded.append(max(prefixes, key=len))
        return tuple(dict.fromkeys(expanded))

    @staticmethod
    def _derive_source_revision(graph: PxgGraph) -> str | None:
        values = {
            value
            for node in graph.nodes_of_kind("screen")
            for value in [node.provenance.get("source_revision")]
            if isinstance(value, str) and value.strip()
        }
        return next(iter(values)) if len(values) == 1 else None
