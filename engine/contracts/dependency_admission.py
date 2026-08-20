# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DependencyAdmission(BaseModel):
    """
    Chapter 9.6's governed admission of one package a worker-produced dependency-
    manifest or lockfile change introduces into the software being built. Owned by
    engine.integration -- admission is evaluated as part of the mandatory diff gates
    (Chapter 9.7's Dependency/vulnerability row) before IntegrationProposal merge, not
    as a capability-registry entry. One row per newly introduced package (top-level or
    transitive-delta member) under one DiffGateReport. status never regresses:
    EVALUATING -> ADMITTED | REJECTED. New top-level packages require the AGENTS.md
    justification (licence, maintenance, why the standard library is insufficient)
    recorded on justification; missing justification is REJECTED (fail closed). Live
    OSV/Grype lookups and Syft-generated lockfile transitives are deferred; this row
    still records the real in-process checks Chapter 9.6 names (licence allow-list,
    advisory catalog, maintenance signal, provenance, transitive delta, typosquat
    heuristic).
    """

    model_config = ConfigDict(extra="forbid")

    admission_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID
    task_id: UUID
    report_id: UUID
    package_name: str
    package_version: str
    ecosystem: Literal["pypi", "npm", "crates", "go", "unknown"]
    is_top_level: bool
    licence: str | None = None
    maintenance_signal: Literal["ok", "warn", "unknown", "critical"]
    provenance: Literal["registry", "unsigned", "unknown", "justified"]
    vulnerability_ids: list[str]
    typosquat_of: str | None = None
    justification: dict[str, object] | None = None
    transitive_delta: int | None = None
    status: Literal["EVALUATING", "ADMITTED", "REJECTED"]
    blocking_reason: str | None = None
    created_at: datetime
    updated_at: datetime
