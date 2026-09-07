# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FrontendAttentionAcknowledgement(BaseModel):
    """
    DDE-069 durable project attention acknowledgement. It suppresses only the
    acknowledged derived attention fingerprint; it never resolves or mutates the
    underlying coverage/PXG/QA source.
    """

    model_config = ConfigDict(extra="forbid")

    acknowledgement_id: UUID
    tenant_id: UUID
    project_id: UUID
    attention_key: str
    acknowledged_by: UUID
    acknowledged_at: datetime
    created_at: datetime
    updated_at: datetime
