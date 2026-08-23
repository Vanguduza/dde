# GENERATED from schemas/. Do not edit.

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PredicateSpec(BaseModel):
    """PredicateSpec nested contract."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["unique_columns", "inclusion_column", "tuple_condition"]
    table_ref: str
    columns: list[str] | None = None
    allowed_values: list[str] | None = None
    condition: str | None = None
    where: list[str] | None = None


class DomainInvariant(BaseModel):
    """
    Chapter 11.5 named, versioned executable check over a real datastore, declared like
    code. The definition is immutable (Chapter 3.10): a material change registers a new
    definition_version content-hashed over the definition fields, never an overwrite.
    predicate_kind admits only the deterministic structural predicates this engine can
    genuinely evaluate (unique_columns, inclusion_column, tuple_condition); free-form
    SQL is deliberately refused so an invariant stays declarative and auditable.
    financial_state marks Chapter 11.5's human-visibility class: a failing financial
    invariant is never auto-repaired without a repair task.
    """

    model_config = ConfigDict(extra="forbid")

    invariant_id: UUID
    tenant_id: UUID
    project_id: UUID
    mission_id: UUID | None = None
    name: str
    description: str
    predicate: PredicateSpec
    financial_state: bool
    required_fixture_class: str
    product_env_class: Literal[
        "ephemeral_preview",
        "integration",
        "staging",
        "production",
    ]
    definition_version: str
    status: Literal["ACTIVE", "RETIRED"]
    created_by: str
    created_at: datetime
    updated_at: datetime
