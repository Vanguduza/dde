# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ValidationReport(BaseModel):
    """Deterministic TaskGraph validation result from Chapter 4.3."""

    model_config = ConfigDict(extra="forbid")

    valid: bool
    error_codes: list[str]
    messages: list[str]
