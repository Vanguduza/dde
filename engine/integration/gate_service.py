"""Production Chapter 9.7 mandatory diff gates and Chapter 9.6 dependency
admission -- the sole writer of `diff_gate_reports` /
`dependency_admissions` rows in PostgreSQL (Chapter 3.5, 3.8). Wired into
the real merge-queue path: `engine.integration.service.
IntegrationQueueService.integrate` runs these gates at Chapter 10.4 step 3
(VALIDATING, after the WriteScopeLease scope check, before the merge
candidate is verified). A worker-produced diff that fails any blocking
gate is REJECTED and, for secret detection, quarantined -- it never
reaches the mission branch.

**Why this lives in `engine.integration`, not a capability registry.**
Chapter 9.7 is explicit: these are "blocking verification steps rather
than registry entries". Chapter 9.5's tool-admission pipeline and
Chapter 9.1's capability catalog are the wrong home; DDE-016's
`engine.capabilities.service` already deferred this work here.

**Scanner honesty (flagged Stage 2 interpretation).** Chapter 9.6–9.7
name Gitleaks, Semgrep, OSV/Grype and Syft as the tools. AGENTS.md
forbids adding a dependency without licence/maintenance/stdlib
justification, and those tools are external binaries, not Python packages
this control plane can import. This mission therefore implements real,
in-process evaluators (`engine.integration.gates`) that inspect the
actual git diff and proposed-revision blobs:

  - Secret detection: real regex ruleset covering the planted-secret
    class Chapter 18.2's S2 fixture requires (AWS-style keys, private-key
    PEM headers, GitHub PATs). The Gitleaks CLI is not invoked.
  - Static analysis: in-process rules over added lines. The Semgrep CLI
    is not invoked; DDE-045's `capability.security` reuses the same
    in-process rules for whole-workspace SAST.
  - Dependency/vulnerability: parse real manifests in the diff; admit
    against an in-process advisory catalog, SPDX allow-list, typosquat
    heuristic, justification requirement for new top-level packages, and
    a transitive-delta threshold. Live OSV/Grype HTTP lookups are not
    performed.
  - Licence header: SPDX/copyright header required on newly added source
    files. Donor Lab ingest (DDE-046) persists artifacts; provenance
    taint into tasks/diffs (§13.8) remains DDE-047 — this gate cannot
    consult a taint graph that does not exist yet.
  - Forbidden paths: CI config, security policy, migrations, `.git`
    internals -- always blocked (approval is DDE-026; without it the
    fail-closed outcome is REJECTED).
  - SBOM: a real CycloneDX 1.5 document generated from declared
    manifests at the proposed revision, persisted on the report,
    content-hashed, and gated (a component matching a REJECTED admission
    fails the report). The Syft CLI is not invoked.

A worker cannot disable, weaken or reconfigure these gates:
`engine.integration.gates` lives in the control plane, outside the task
workspace, and is not read from the worktree.

**What this module explicitly does NOT do** -- deferred, not stubbed:
  - Invoking the Gitleaks / Semgrep / Grype / Syft binaries.
  - Live OSV.dev HTTP lookups.
  - Full lockfile-transitive SBOM (declared manifests only; lockfile
    diffs contribute a transitive-delta count).
  - Donor taint propagation (DDE-047; ingest tables land in DDE-046).
  - Approval records for new top-level deps above the autonomy ceiling
    (DDE-026); missing justification itself blocks, which is the
    stricter fail-closed default of Chapter 9.6's AGENTS.md rule.
  - Wiring SBOM bytes into `engine.verification`'s `evidence` table
    (owned by verification per Chapter 3.8). The document is stored on
    `diff_gate_reports` and emitted as a `DiffGateEvaluated` event
    carrying `sbom_content_hash`; Evidence-pipeline binding is the
    verification owner's concern.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.command_idempotency import CommandIdempotency
from engine.contracts.dependency_admission import DependencyAdmission
from engine.contracts.diff_gate_report import DiffGateFinding, DiffGateReport
from engine.contracts.integration_proposal import IntegrationProposal
from engine.core.clock import Clock, SystemClock
from engine.core.errors import DdeError
from engine.core.hashing import canonical_json, sha256_hex
from engine.core.ids import uuid7
from engine.core.state_machine import transition
from engine.events.idempotency import CommandLedger
from engine.events.service import EventService
from engine.integration import git
from engine.integration.gates import (
    GateEvaluation,
    PackageDecision,
    ScanFinding,
    evaluate_diff,
    is_dependency_manifest,
    is_lockfile,
)
from engine.integration.hashing import gate_request_hash
from engine.integration.repository import (
    DependencyAdmissionRepository,
    DiffGateReportRepository,
)
from engine.integration.states import DIFF_GATE_REPORT_TRANSITIONS
from engine.truth.db import PostgresUnitOfWork, open_unit_of_work

T = TypeVar("T")


class DiffGateService:
    """Async, PostgreSQL-backed writer for `diff_gate_reports` and
    `dependency_admissions`. Each public method opens and commits its own
    unit of work unless one is supplied, so a caller composing a
    cross-module transaction (Chapter 3.5) -- specifically
    `IntegrationQueueService.integrate` -- can share it instead."""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventService | None = None,
        commands: CommandLedger | None = None,
        reports: DiffGateReportRepository | None = None,
        admissions: DependencyAdmissionRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine = engine
        self._events = events or EventService(engine)
        self._commands = commands or CommandLedger(engine)
        self._reports = reports or DiffGateReportRepository()
        self._admissions = admissions or DependencyAdmissionRepository()
        self._clock = clock or SystemClock()

    async def _run(
        self,
        uow: PostgresUnitOfWork | None,
        tenant_id: UUID,
        project_id: UUID,
        body: Callable[[PostgresUnitOfWork], Awaitable[T]],
    ) -> T:
        if uow is not None:
            return await body(uow)
        async with open_unit_of_work(
            self._engine, tenant_id=tenant_id, project_id=project_id
        ) as owned:
            result = await body(owned)
            await owned.commit()
            return result

    async def evaluate(
        self,
        *,
        proposal: IntegrationProposal,
        repo_root: Path,
        base_revision: str,
        proposed_revision: str,
        changed_paths: list[str],
        uow: PostgresUnitOfWork | None = None,
    ) -> DiffGateReport:
        """Evaluate every Chapter 9.7 gate against the real
        `base_revision..proposed_revision` diff and persist the report.
        Idempotent on `(proposal_id, base, proposed)` via CommandLedger."""
        digest = gate_request_hash(
            proposal_id=proposal.proposal_id,
            base_revision=base_revision,
            proposed_revision=proposed_revision,
        )
        idempotency_key = (
            f"diff-gate:{proposal.proposal_id}:{base_revision}:{proposed_revision}"
        )

        async def _op(active: PostgresUnitOfWork) -> DiffGateReport:
            record, is_new = await self._commands.begin(
                tenant_id=proposal.tenant_id,
                project_id=proposal.project_id,
                idempotency_key=idempotency_key,
                request_hash=digest,
                uow=active,
            )
            if not is_new:
                return await self._replay_or_raise(active, record)

            now = self._clock.now()
            report = DiffGateReport(
                report_id=uuid7(),
                tenant_id=proposal.tenant_id,
                project_id=proposal.project_id,
                mission_id=proposal.mission_id,
                task_id=proposal.task_id,
                proposal_id=proposal.proposal_id,
                command_id=record.command_id,
                idempotency_key=idempotency_key,
                request_hash=digest,
                base_revision=base_revision,
                proposed_revision=proposed_revision,
                changed_paths=list(changed_paths),
                status="EVALUATING",
                findings=[],
                quarantined=False,
                sbom_document={},
                sbom_content_hash="",
                created_at=now,
                updated_at=now,
            )
            await self._reports.insert_report(active.connection, report)
            await self._events.append(
                tenant_id=proposal.tenant_id,
                project_id=proposal.project_id,
                event_type="DiffGateEvaluating",
                aggregate_type="diff_gate_report",
                aggregate_id=report.report_id,
                mission_id=proposal.mission_id,
                task_id=proposal.task_id,
                payload={
                    "proposal_id": str(proposal.proposal_id),
                    "base_revision": base_revision,
                    "proposed_revision": proposed_revision,
                },
                uow=active,
            )

            outcome = self._scan(
                repo_root=repo_root,
                base_revision=base_revision,
                proposed_revision=proposed_revision,
                changed_paths=changed_paths,
            )
            target_status = "PASSED" if outcome.passed else "FAILED"
            findings = [_to_finding(item) for item in outcome.findings]
            for decision in outcome.admissions:
                admission = _to_admission(
                    decision,
                    report=report,
                    now=now,
                )
                await self._admissions.insert_admission(active.connection, admission)

            updated = await self._finish(
                active,
                report,
                target_status=target_status,
                findings=findings,
                quarantined=outcome.quarantined,
                sbom_document=outcome.sbom_document,
                sbom_content_hash=outcome.sbom_content_hash,
            )
            if outcome.quarantined:
                await self._events.append(
                    tenant_id=updated.tenant_id,
                    project_id=updated.project_id,
                    event_type="SecurityFindingRaised",
                    aggregate_type="diff_gate_report",
                    aggregate_id=updated.report_id,
                    mission_id=updated.mission_id,
                    task_id=updated.task_id,
                    payload={
                        "gate": "secret_detection",
                        "proposal_id": str(updated.proposal_id),
                    },
                    uow=active,
                )
            await self._commands.complete(
                tenant_id=proposal.tenant_id,
                project_id=proposal.project_id,
                command_id=record.command_id,
                result={"report_id": str(updated.report_id)},
                uow=active,
            )
            return updated

        return await self._run(uow, proposal.tenant_id, proposal.project_id, _op)

    def verify_sbom(self, report: DiffGateReport) -> bool:
        """Round-trip integrity: the persisted document still hashes to
        `sbom_content_hash`. A mismatch is a control-plane defect, not a
        worker finding."""
        return sha256_hex(canonical_json(report.sbom_document)) == (
            report.sbom_content_hash
        )

    async def get_report(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        report_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> DiffGateReport:
        async def _op(active: PostgresUnitOfWork) -> DiffGateReport:
            return await self._require_report(active, report_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_for_proposal(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        proposal_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[DiffGateReport]:
        async def _op(active: PostgresUnitOfWork) -> list[DiffGateReport]:
            return await self._reports.list_for_proposal(active.connection, proposal_id)

        return await self._run(uow, tenant_id, project_id, _op)

    async def list_admissions(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        report_id: UUID,
        uow: PostgresUnitOfWork | None = None,
    ) -> list[DependencyAdmission]:
        async def _op(active: PostgresUnitOfWork) -> list[DependencyAdmission]:
            return await self._admissions.list_for_report(active.connection, report_id)

        return await self._run(uow, tenant_id, project_id, _op)

    def _scan(
        self,
        *,
        repo_root: Path,
        base_revision: str,
        proposed_revision: str,
        changed_paths: list[str],
    ) -> GateEvaluation:
        unified = git.diff_unified(repo_root, base_revision, proposed_revision)
        new_paths = git.diff_name_only_filter(
            repo_root, base_revision, proposed_revision, "A"
        )
        proposed_blobs = {
            path: git.show_blob(repo_root, proposed_revision, path)
            for path in changed_paths
        }
        manifest_paths = [
            path
            for path in git.ls_tree_names(repo_root, proposed_revision)
            if is_dependency_manifest(path)
        ]
        declared = [path for path in manifest_paths if not is_lockfile(path)]
        proposed_manifests = {
            path: git.show_blob(repo_root, proposed_revision, path) for path in declared
        }
        changed_manifests = [
            path for path in changed_paths if is_dependency_manifest(path)
        ]
        base_manifests = {
            path: git.show_blob(repo_root, base_revision, path)
            for path in changed_manifests
        }
        proposed_changed_manifests = {
            path: git.show_blob(repo_root, proposed_revision, path)
            for path in changed_manifests
        }
        # Justification files are not manifests; include their blobs.
        for path in changed_paths:
            if path not in proposed_blobs:
                proposed_blobs[path] = git.show_blob(repo_root, proposed_revision, path)
        return evaluate_diff(
            changed_paths=changed_paths,
            unified_diff=unified,
            proposed_blobs=proposed_blobs,
            base_manifest_blobs=base_manifests,
            proposed_manifest_blobs={
                **proposed_manifests,
                **proposed_changed_manifests,
            },
            new_paths=new_paths,
        )

    async def _finish(
        self,
        active: PostgresUnitOfWork,
        current: DiffGateReport,
        *,
        target_status: str,
        findings: list[DiffGateFinding],
        quarantined: bool,
        sbom_document: dict[str, object],
        sbom_content_hash: str,
    ) -> DiffGateReport:
        next_status = transition(
            current.status, target_status, DIFF_GATE_REPORT_TRANSITIONS
        )
        now = self._clock.now()
        rowcount = await self._reports.update_fields(
            active.connection,
            current.report_id,
            fields={
                "status": next_status,
                "findings": [item.model_dump() for item in findings],
                "quarantined": quarantined,
                "sbom_document": sbom_document,
                "sbom_content_hash": sbom_content_hash,
                "updated_at": now,
            },
        )
        if rowcount != 1:
            raise DdeError(
                "VERSION_CONFLICT",
                "Unknown diff gate report",
                details={"report_id": str(current.report_id)},
            )
        updated = await self._require_report(active, current.report_id)
        await self._events.append(
            tenant_id=updated.tenant_id,
            project_id=updated.project_id,
            event_type="DiffGateEvaluated",
            aggregate_type="diff_gate_report",
            aggregate_id=updated.report_id,
            mission_id=updated.mission_id,
            task_id=updated.task_id,
            payload={
                "status": updated.status,
                "quarantined": updated.quarantined,
                "sbom_content_hash": updated.sbom_content_hash,
                "failed_gates": [
                    item.gate for item in updated.findings if not item.passed
                ],
            },
            uow=active,
        )
        return updated

    async def _replay_or_raise(
        self, active: PostgresUnitOfWork, record: CommandIdempotency
    ) -> DiffGateReport:
        if record.status == "completed" and record.result is not None:
            report_id = record.result.get("report_id")
            if not isinstance(report_id, str):
                raise DdeError(
                    "VERSION_CONFLICT",
                    "Completed diff-gate command is missing report_id",
                    details={"idempotency_key": record.idempotency_key},
                )
            return await self._require_report(active, UUID(report_id))
        if record.status == "failed":
            raise DdeError(
                "VERSION_CONFLICT",
                "Command previously failed; refusing to re-execute",
                details={"idempotency_key": record.idempotency_key},
            )
        raise DdeError(
            "VERSION_CONFLICT",
            "Command is already in progress",
            retryable=True,
            details={"idempotency_key": record.idempotency_key},
        )

    async def _require_report(
        self, active: PostgresUnitOfWork, report_id: UUID
    ) -> DiffGateReport:
        record = await self._reports.get_by_id(active.connection, report_id)
        if record is None:
            raise DdeError(
                "POLICY_DENIED",
                "Unknown diff gate report",
                details={"report_id": str(report_id)},
            )
        return record


def _to_finding(item: ScanFinding) -> DiffGateFinding:
    return DiffGateFinding.model_validate(
        {
            "gate": item.gate,
            "tool": item.tool,
            "severity": item.severity,
            "blocking": item.blocking,
            "passed": item.passed,
            "summary": item.summary,
            "details": item.details,
        }
    )


def _to_admission(
    decision: PackageDecision,
    *,
    report: DiffGateReport,
    now: datetime,
) -> DependencyAdmission:
    return DependencyAdmission.model_validate(
        {
            "admission_id": uuid7(),
            "tenant_id": report.tenant_id,
            "project_id": report.project_id,
            "mission_id": report.mission_id,
            "task_id": report.task_id,
            "report_id": report.report_id,
            "package_name": decision.package_name,
            "package_version": decision.package_version,
            "ecosystem": decision.ecosystem,
            "is_top_level": decision.is_top_level,
            "licence": decision.licence,
            "maintenance_signal": decision.maintenance_signal,
            "provenance": decision.provenance,
            "vulnerability_ids": list(decision.vulnerability_ids),
            "typosquat_of": decision.typosquat_of,
            "justification": decision.justification,
            "transitive_delta": decision.transitive_delta,
            "status": decision.status,
            "blocking_reason": decision.blocking_reason,
            "created_at": now,
            "updated_at": now,
        }
    )
