"""Chapter 11.5 deterministic predicate compilation and evaluation.

Three structural predicate kinds — the ones this engine can genuinely,
deterministically evaluate over real rows:

- `unique_columns`  — no group of the declared columns holds more than
  one row;
- `inclusion_column` — every value of the declared column is inside a
  closed allow-list (the "every accepted requirement links to a charter"
  class of membership condition);
- `tuple_condition`  — an aggregate condition per tuple, e.g.
  `sum(amount) = 0` grouped by declared columns.

Safety posture: identifiers are validated against a strict SQL identifier
grammar and quoted; values are bound as parameters; where-filters are
restricted to separator-free fragments. Nothing user-supplied is ever
interpolated in a way that can change statement structure, so a predicate
stays declarative and auditable end to end. Free-form SQL is not a
predicate kind — it is refused at compile time.

`judge_rows` is pure: same rows in, same verdict out, no clock and no
randomness. Determinism at this layer is what makes the service layer's
idempotent re-run guarantee honest (Chapter 12.4/12.5).
"""

from __future__ import annotations

import re
from typing import Final

from engine.contracts.domain_invariant import PredicateSpec
from engine.core.errors import DdeError

PREDICATE_KINDS: Final[frozenset[str]] = frozenset(
    {"unique_columns", "inclusion_column", "tuple_condition"}
)

_IDENTIFIER: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_QUALIFIED_TABLE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$"
)

_NUMERIC_CONDITION: Final[re.Pattern[str]] = re.compile(
    r"^(sum|count|min|max|avg)\s*\(\s*[A-Za-z_][A-Za-z0-9_]*\s*\)\s*"
    r"(=|<>|!=|<|>|<=|>=)\s*(-?\d+(\.\d+)?)$",
    re.IGNORECASE,
)

_MAX_VIOLATION_GROUPS = 20


def _quote_identifier(name: str) -> str:
    if not _IDENTIFIER.match(name):
        raise DdeError(
            "POLICY_DENIED",
            "Predicate identifiers must be plain SQL identifiers; free-form "
            "SQL is not an invariant predicate (Chapter 11.5)",
            details={"identifier": name},
        )
    return f'"{name}"'


def _qualified_table(table_ref: str) -> str:
    if not _QUALIFIED_TABLE.match(table_ref):
        raise DdeError(
            "POLICY_DENIED",
            "table_ref must be an optionally schema-qualified table name",
            details={"table_ref": table_ref},
        )
    return ".".join(f'"{part}"' for part in table_ref.split("."))


def _where_fragment(spec: PredicateSpec) -> str:
    clauses = list(spec.where or [])
    for clause in clauses:
        if ";" in clause or "--" in clause or "/*" in clause:
            raise DdeError(
                "POLICY_DENIED",
                "Predicate where-filters must not contain statement "
                "separators or comments",
                details={"where": clause},
            )
    if not clauses:
        return ""
    return " WHERE " + " AND ".join(clauses)


def _select(sql: str) -> str:
    """The one statement-assembly point. Every fragment reaching it is
    either a validated identifier (quoted), a grammar-checked aggregate
    condition, or a separator-free where-filter; values are always bound
    parameters, never text."""
    return sql  # noqa: S608


def compile_predicate(spec: PredicateSpec) -> tuple[str, dict[str, object]]:
    """Compile one predicate into `(parameterised_sql, params)`.

    Every compiled statement returns violation rows whose single column is
    the offending group rendered as text, so the recorder can attach
    concrete evidence instead of a bare boolean.
    """
    if spec.kind not in PREDICATE_KINDS:
        raise DdeError(
            "POLICY_DENIED",
            f"Unknown predicate kind {spec.kind!r}; Chapter 11.5 invariants "
            "are declared with the structural predicates only",
            details={"kind": spec.kind},
        )
    table = _qualified_table(spec.table_ref)
    limit_params: dict[str, object] = {"_limit": _MAX_VIOLATION_GROUPS}

    if spec.kind == "unique_columns":
        columns = spec.columns or []
        if not columns:
            raise DdeError(
                "POLICY_DENIED",
                "unique_columns declares the columns it deduplicates on",
                details={"kind": spec.kind},
            )
        quoted = [_quote_identifier(name) for name in columns]
        key_list = ", ".join(quoted)
        key_text = ", ".join(f"COALESCE({name}::text, 'NULL')" for name in quoted)
        sql = _select(
            f"SELECT {key_text} AS violation FROM {table}"  # noqa: S608
            f"{_where_fragment(spec)} GROUP BY {key_list} "  # noqa: S608
            "HAVING COUNT(*) > 1 LIMIT :_limit"
        )
        return sql, dict(limit_params)

    if spec.kind == "inclusion_column":
        allowed = spec.allowed_values
        if not allowed:
            raise DdeError(
                "POLICY_DENIED",
                "inclusion_column declares the closed allow-list it checks "
                "membership against",
                details={"kind": spec.kind},
            )
        if len(spec.columns or []) != 1:
            raise DdeError(
                "POLICY_DENIED",
                "inclusion_column names exactly one column",
                details={"kind": spec.kind},
            )
        column = _quote_identifier((spec.columns or [""])[0])
        base_where = _where_fragment(spec)
        connector = " AND" if base_where else " WHERE"
        sql = _select(
            f"SELECT {column}::text AS violation FROM {table}"  # noqa: S608
            f"{base_where}{connector} {column} <> ALL(:allowed) LIMIT :_limit"  # noqa: S608
        )
        return sql, {"allowed": list(allowed), **limit_params}

    condition = (spec.condition or "").strip()
    if not _NUMERIC_CONDITION.match(condition):
        raise DdeError(
            "POLICY_DENIED",
            "tuple_condition accepts `aggregate(column) <op> number` only; "
            "free-form expressions are refused (Chapter 11.5)",
            details={"condition": spec.condition or ""},
        )
    group_columns = [_quote_identifier(name) for name in (spec.columns or [])]
    if group_columns:
        key_list = ", ".join(group_columns)
        key_text = ", ".join(
            f"COALESCE({name}::text, 'NULL')" for name in group_columns
        )
        sql = _select(
            f"SELECT {key_text} AS violation FROM {table}"  # noqa: S608
            f"{_where_fragment(spec)} GROUP BY {key_list} "  # noqa: S608
            f"HAVING NOT ({condition}) LIMIT :_limit"
        )
    else:
        sql = _select(
            f"SELECT {condition}::text AS violation FROM {table}"  # noqa: S608
            f"{_where_fragment(spec)} HAVING NOT ({condition}) LIMIT :_limit"  # noqa: S608
        )
    return sql, dict(limit_params)


def judge_rows(rows_checked: int, violation_count: int) -> tuple[str, int]:
    """Pure verdict over collected rows: PASSED exactly when zero
    violations were observed over the rows actually checked."""
    if violation_count > 0:
        return "FAILED", rows_checked
    return "PASSED", rows_checked
