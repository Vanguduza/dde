"""Chapter 11.5 domain invariant engine — the pure halves.

`engine.invariants.predicates`: the three deterministic structural
predicates compile to parameterised SQL; nothing user-supplied is ever
interpolated into the statement text (identifier allow-list + bound
parameters only), and an unknown predicate kind or a non-numeric raw
condition operand is refused at compile time, not at execution time.
Evaluation itself is a pure function of (predicate, rows): same rows in,
same verdict out — no clock, no randomness — which is what makes a
re-run of the same evaluation idempotent at the service layer.

`engine.invariants.states`: the definition lifecycle is deliberately
two-state. A DomainInvariant is declared ACTIVE and leaves the active
set only by retirement (Chapter 3.10: material change = new version, so
there is no DRAFT->APPROVED authoring workflow here); RETIRED is
terminal because evaluations always record which definition_version they
ran against — un-retiring would silently re-attach old semantics.
"""

from __future__ import annotations

import pytest

from engine.contracts.domain_invariant import PredicateSpec
from engine.core.errors import DdeError
from engine.invariants.predicates import (
    PREDICATE_KINDS,
    compile_predicate,
)
from engine.invariants.states import (
    DEFINITION_TRANSITIONS,
    TERMINAL_DEFINITION_STATES,
    assert_transition,
)


def _unique_spec() -> dict[str, object]:
    return {
        "kind": "unique_columns",
        "table_ref": "public.requirements",
        "columns": ["project_id", "slug"],
    }


def test_every_declared_predicate_kind_is_known() -> None:
    assert PREDICATE_KINDS == frozenset(
        {"unique_columns", "inclusion_column", "tuple_condition"}
    )


def test_unique_predicate_compiles_parameterised_group_by() -> None:
    spec = PredicateSpec.model_validate(_unique_spec())
    sql, params = compile_predicate(spec)
    assert 'COALESCE("project_id"::text' in sql
    assert 'GROUP BY "project_id"' in sql
    assert "HAVING COUNT(*) > 1" in sql
    assert params.keys() == {"_limit"}


def test_unique_predicate_requires_columns() -> None:
    spec = PredicateSpec.model_validate({"kind": "unique_columns", "table_ref": "t"})
    with pytest.raises(DdeError):
        compile_predicate(spec)


def test_unique_predicate_rejects_non_identifier_column() -> None:
    spec = PredicateSpec.model_validate(
        {
            "kind": "unique_columns",
            "table_ref": "public.t",
            "columns": ["slug; DROP TABLE tenants"],
        }
    )
    with pytest.raises(DdeError):
        compile_predicate(spec)


def test_inclusion_predicate_binds_allowed_values_as_parameters() -> None:
    spec = PredicateSpec.model_validate(
        {
            "kind": "inclusion_column",
            "table_ref": "public.requirements",
            "columns": ["status"],
            "allowed_values": ["draft", "approved"],
        }
    )
    sql, params = compile_predicate(spec)
    # The allow-list is a bound parameter, never inlined text.
    assert "draft" not in sql and "approved" not in sql
    assert "<> ALL(:allowed)" in sql
    assert params["allowed"] == ["draft", "approved"]


def test_inclusion_predicate_requires_allowed_values() -> None:
    spec = PredicateSpec.model_validate(
        {
            "kind": "inclusion_column",
            "table_ref": "public.requirements",
            "columns": ["status"],
        }
    )
    with pytest.raises(DdeError):
        compile_predicate(spec)


def test_tuple_condition_rejects_non_numeric_operand() -> None:
    spec = PredicateSpec.model_validate(
        {
            "kind": "tuple_condition",
            "table_ref": "public.journal_lines",
            "condition": "sum(amount) = 'zero'",
        }
    )
    with pytest.raises(DdeError):
        compile_predicate(spec)


def test_tuple_condition_accepts_numeric_operand_and_where_filters() -> None:
    spec = PredicateSpec.model_validate(
        {
            "kind": "tuple_condition",
            "table_ref": "public.journal_lines",
            "condition": "sum(amount) <> 0",
            "where": ["entry_id IS NOT NULL"],
        }
    )
    sql, _params = compile_predicate(spec)
    assert "sum(amount)" in sql
    assert "entry_id IS NOT NULL" in sql


def test_unknown_kind_is_refused_at_compile_time() -> None:
    # model_construct bypasses validation on purpose: the contract's
    # Literal kind refuses unknown kinds at the boundary, and this pins
    # the second, deeper refusal inside compile_predicate itself.
    spec = PredicateSpec.model_construct(
        kind="raw_sql",
        table_ref="t",
        columns=None,
        allowed_values=None,
        condition=None,
        where=None,
    )
    with pytest.raises(DdeError):
        compile_predicate(spec)


# --- definition lifecycle ---------------------------------------------------


def test_definition_lifecycle_is_active_to_retired_only() -> None:
    assert set(DEFINITION_TRANSITIONS) == {"ACTIVE", "RETIRED"}
    assert DEFINITION_TRANSITIONS["ACTIVE"] == frozenset({"RETIRED"})
    assert DEFINITION_TRANSITIONS["RETIRED"] == frozenset()


def test_retired_is_terminal() -> None:
    assert TERMINAL_DEFINITION_STATES == frozenset({"RETIRED"})
    with pytest.raises(DdeError):
        assert_transition("RETIRED", "ACTIVE")


def test_illegal_transition_is_typed_and_names_both_ends() -> None:
    try:
        assert_transition("RETIRED", "ACTIVE")
    except DdeError as error:
        assert error.error_code == "VERSION_CONFLICT"
        assert error.details is not None
        assert error.details.get("from") == "RETIRED"
        assert error.details.get("to") == "ACTIVE"
    else:
        raise AssertionError("illegal transition must raise")


# --- pure verdict -----------------------------------------------------------


def test_verdict_is_pure_over_rows() -> None:
    from engine.invariants.predicates import judge_rows

    violations_empty: list[object] = []
    assert judge_rows(rows_checked=0, violation_count=0) == ("PASSED", 0)
    status, rows = judge_rows(rows_checked=7, violation_count=2)
    assert (status, rows) == ("FAILED", 7)
    assert violations_empty == []


# --- definition version hashing ---------------------------------------------


def _hash_kwargs() -> dict[str, object]:
    from uuid import uuid4

    return {
        "tenant_id": uuid4(),
        "project_id": uuid4(),
        "name": "requirement_statement_unique",
        "description": "Requirement statements are unique within a project",
        "predicate": PredicateSpec.model_validate(
            {
                "kind": "unique_columns",
                "table_ref": "public.requirements",
                "columns": ["project_id", "statement"],
            }
        ),
        "financial_state": False,
        "required_fixture_class": "erp-baseline",
        "product_env_class": "ephemeral_preview",
    }


def test_definition_hash_is_deterministic_and_covers_definition_fields() -> None:
    from engine.invariants.hashing import definition_version_hash

    kwargs = _hash_kwargs()
    first = definition_version_hash(**kwargs)
    second = definition_version_hash(**kwargs)
    assert first == second
    assert len(first) == 64
    # Any material change to a definition field mints a different version.
    changed_description = dict(kwargs, description="tighter wording")
    changed_predicate = dict(
        kwargs,
        predicate=PredicateSpec.model_validate(
            {
                "kind": "unique_columns",
                "table_ref": "public.requirements",
                "columns": ["project_id", "slug"],
            }
        ),
    )
    assert definition_version_hash(**changed_description) != first
    assert definition_version_hash(**changed_predicate) != first
