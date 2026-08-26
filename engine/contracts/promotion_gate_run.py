# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PromotionGateRun(BaseModel):
    """
    Chapter 5.13's promotion-gate evaluation for a candidate context policy (push, pull,
    or semantic_retrieval_enabled) against the current certified baseline, over the
    frozen eval corpus. Durable identity (`run_id`) plus an `idempotency_key` (unique
    per tenant) so re-submitting the same evaluation request observes the same run
    instead of recomputing it; `status` is the observable async state. This deployment
    computes critical_coverage, contradiction_rate (compile-time CONFLICTED rate vs
    baseline), and token_cost_per_verified_success (compile-token means; a rise FAILs).
    context_attributed_failure_rate and task_success_on_corpus remain deferred
    (EDR-0003: they need worker-verification replay per eval case, not a compile()
    call). `decision` therefore never claims full Chapter 5.13 promotion: it is
    `INSUFFICIENT_CORPUS`, `FAIL`, or `PARTIAL_PASS_IMPLEMENTED_GATES_ONLY`. Owned by
    engine.context.
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
