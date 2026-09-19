# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AutomationWorkflowDefinition(BaseModel):
    """
    EDR-0019 Epic J authored automation workflow. DDE owns intent: an automation runtime
    is a target runtime effect under CapabilityLease/ExternalEffect/verifier law, never
    a DDE WorkerAdapter and never a task orchestrator. A workflow may not decide what
    DDE does next.
    """

    model_config = ConfigDict(extra="forbid")

    definition_id: UUID
    tenant_id: UUID
    project_id: UUID
    runtime_kind: Literal["N8N", "OTHER"]
    name: str
    intent_summary: str
    authored_by: Literal["OPERATOR", "DDE_TASK", "PATTERN_DESCRIPTOR"]
    derived_from_descriptor_id: UUID | None = None
    definition_hash: str
    node_inventory: list[str]
    created_at: datetime
    updated_at: datetime
