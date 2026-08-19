# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Error(BaseModel):
    """Gateway error contract from Chapter 15.5."""

    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    retryable: bool
    details: dict[str, object] | None = None
    correlation_id: str
