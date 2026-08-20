# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DiffGateFinding(BaseModel):
    """DiffGateFinding nested contract."""

    model_config = ConfigDict(extra="forbid")

    gate: Literal[
        "secret_detection",
        "static_analysis",
        "dependency_vulnerability",
        "licence_header",
        "forbidden_path",
    ]
    tool: str
    severity: Literal["info", "warn", "error", "critical"]
    blocking: bool
    passed: bool
    summary: str
    details: dict[str, object] | None = None


class DiffGateReport(BaseModel):
    """
    Chapter 9.7's mandatory diff-gate evaluation of one worker-produced diff, run as a
    blocking verification step on every IntegrationProposal before merge (Chapter 10.4
    step 3) rather than as a capability-registry entry. Owned by engine.integration
    (Chapter 3.8: Integration is the owner of merge-queue state; Chapter 9.7: these
    gates are not registry entries). status never regresses: EVALUATING -> PASSED |
    FAILED, enforced by engine.integration.states.DIFF_GATE_REPORT_TRANSITIONS. A FAILED
    secret-detection finding also sets quarantined=true (Chapter 9.7: 'Block, quarantine
    the diff, raise a security finding'). sbom_document is a real CycloneDX 1.5 subset
    generated per integration (Chapter 9.6) and content-addressed by sbom_content_hash
    -- not a placeholder string. command_id is engine.events.idempotency.CommandLedger's
    identity at evaluate() time. proposal_id is a real FK: a report is always the
    evaluation of one queued proposal's actual git diff.
    """

    model_config = ConfigDict(extra="forbid")

    report_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    proposal_id: UUID
    command_id: UUID
    idempotency_key: str
    request_hash: str
    base_revision: str
    proposed_revision: str
    changed_paths: list[str]
    status: Literal["EVALUATING", "PASSED", "FAILED"]
    findings: list[DiffGateFinding]
    quarantined: bool
    sbom_document: dict[str, object]
    sbom_content_hash: str
    created_at: datetime
    updated_at: datetime
