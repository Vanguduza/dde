# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BoundedLoopDefinition(BaseModel):
    """
    Verifier-terminated bounded convergence loop. Uncertain side effects cannot be
    blindly retried.
    """

    model_config = ConfigDict(extra="forbid")

    loop_id: str
    entry_condition: str
    objective: str
    max_cycles: int
    max_steps: int
    steps: list[dict[str, object]]
    allowed_resource_ids: list[UUID]
    allowed_capabilities: list[str]
    budget: dict[str, object]
    verifier: str
    checkpoints: list[str]
    failure_policy: str
    rollback_policy: str
