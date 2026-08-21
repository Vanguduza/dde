# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PromotionGateRun(BaseModel):
    """
    Chapter 5.13's promotion-gate evaluation for a candidate context policy (e.g.
    `semantic_retrieval_enabled=True`) against the current certified baseline, over the
    frozen eval corpus. Durable identity (`run_id`) plus an `idempotency_key` (unique
    per tenant) so re-submitting the same evaluation request observes the same run
    instead of recomputing it; `status` is the observable async state. Chapter 5.13
    lists five promotion gates; `gate_results` only ever contains the subset this
    deployment can compute today (`critical_coverage` -- see EDR-0003 for the other
    four, which need the Chapter 5.11 failure-attribution and worker-verification loop
    wired to eval cases and are not computed here). `decision` therefore never claims
    full Chapter 5.13 promotion: it is `INSUFFICIENT_CORPUS` (corpus below the Chapter
    5.13 minimum-viable size/diversity), `FAIL` (an implemented gate regressed), or
    `PARTIAL_PASS_IMPLEMENTED_GATES_ONLY` (every implemented gate held; the remaining
    gates are still unimplemented). Owned by engine.context.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    tenant_id: UUID
    project_id: UUID
    idempotency_key: str
    candidate_label: str
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]
    corpus_size: int
    task_class_count: int
    adversarial_count: int
    decision: (
        Literal["INSUFFICIENT_CORPUS", "FAIL", "PARTIAL_PASS_IMPLEMENTED_GATES_ONLY"]
        | None
    ) = None
    gate_results: dict[str, object]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
