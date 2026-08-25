"""In-process db_assertion runner for capability.database (DDE-049).

Chapter 9.6 discipline: no vendor database tooling. The asserter opens its
own short-lived engine per check (a verification probe, not a request
path), refuses any non-SELECT statement text before execution, and requires
each statement to return exactly one boolean row. A statement that errors
is a genuine FAILED outcome (evidence the assertion does not hold), never
an unhandled exception.
"""

from __future__ import annotations

import json
import re
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from engine.capabilities.database import (
    DatabaseAssertionResult,
    DatabaseAssertionSpec,
)
from engine.core.errors import DdeError

_FORBIDDEN_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "truncate",
    "grant",
    "revoke",
    "copy",
    "vacuum",
    "call",
    "do",
)

#: Word-boundary match so `created_at` in a column name is not "create".
_FORBIDDEN_RE = re.compile(
    r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE
)


def _validate_single_readonly_select(statement: str) -> None:
    stripped = statement.strip().rstrip(";")
    if ";" in stripped:
        raise DdeError(
            "VALIDATION_FAILED",
            "db_assertion statements must be a single SELECT "
            "(multiple statements refused)",
            details={},
        )
    first_word = stripped.split(None, 1)[0].lower() if stripped else ""
    if first_word != "select" and first_word not in ("with",):
        raise DdeError(
            "POLICY_DENIED",
            f"db_assertion refuses non-read statements (got {first_word!r})",
            details={"statement_prefix": stripped[:60]},
        )
    hit = _FORBIDDEN_RE.search(stripped)
    if hit is not None:
        raise DdeError(
            "POLICY_DENIED",
            f"db_assertion refuses write/DDL keyword {hit.group(0)!r} "
            "inside an assertion",
            details={"statement_prefix": stripped[:60]},
        )


class InProcessDatabaseAsserter:
    async def assert_(self, spec: DatabaseAssertionSpec) -> DatabaseAssertionResult:
        return await _assert_sync(spec)


async def _assert_sync(spec: DatabaseAssertionSpec) -> DatabaseAssertionResult:
    started = time.monotonic()
    if not spec.statements:
        raise DdeError(
            "VALIDATION_FAILED",
            "db_assertion requires at least one statement",
            details={},
        )
    for statement in spec.statements:
        _validate_single_readonly_select(statement)

    engine = create_async_engine(spec.datastore_url)
    results: list[dict[str, object]] = []
    stderr_notes: list[str] = []
    try:
        async with engine.connect() as connection:
            for index, statement in enumerate(spec.statements):
                entry: dict[str, object] = {"index": index}
                try:
                    cursor = await connection.execute(text(statement))
                    row = cursor.fetchone()
                except Exception as exc:
                    # A failing query is evidence the assertion does not
                    # hold on this datastore — record and continue.
                    entry["passed"] = False
                    entry["error"] = str(exc).split("\n")[0][:200]
                    stderr_notes.append(f"#{index}: {entry['error']}")
                    results.append(entry)
                    continue
                scalar = row[0] if row is not None else None
                passed = scalar is True
                entry["passed"] = passed
                entry["value"] = (
                    scalar if isinstance(scalar, bool | int | str) else str(scalar)
                )
                results.append(entry)
    finally:
        await engine.dispose()

    overall = bool(results) and all(item["passed"] is True for item in results)
    payload = {
        "mode": "db_assertion",
        "passed": overall,
        "results": results,
    }
    elapsed = int((time.monotonic() - started) * 1000)
    return DatabaseAssertionResult(
        exit_code=0 if overall else 1,
        stdout=json.dumps(payload, sort_keys=True),
        stderr="; ".join(stderr_notes),
        duration_ms=elapsed,
        timed_out=False,
        passed=overall,
    )
