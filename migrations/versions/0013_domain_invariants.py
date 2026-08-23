"""Chapter 11.5 tables (DDE-039) -- domain_invariants and
invariant_evaluations.

Replays the statements for the two new tables from the canonical
generated `schemas/sql/0001_stage1.sql` (migration 0012's pattern), so
the schema bundle stays the single source of truth. One downgrade drops
both tables wholesale. Tenant/project RLS follows Chapter 3.2's
fail-closed GUC predicate, same shape as every stored table.

Idempotent exactly like 0012: the bundle 0001 replays on a fresh
database ALREADY emits both tables (they live in the generated SQL), so
this migration no-ops when they exist and only forward-applies onto a
database stopped at 0011 or earlier.
"""

from __future__ import annotations

import re
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"

_TABLES = ("domain_invariants", "invariant_evaluations")

#: Matches the tables AS OBJECTS (CREATE TABLE x / ALTER TABLE x /
#: POLICY ... ON x), not any textual mention -- `acceptance_oracles`
#: carries a JSONB *column* named `domain_invariants`, and selecting its
#: whole CREATE TABLE by substring would replay a foreign table here.
_TABLE_OBJECT = re.compile(
    rf"\b(?:TABLE|ON)\s+(?:{'|'.join(re.escape(name) for name in _TABLES)})\b",
    re.IGNORECASE,
)


def _statements() -> list[str]:
    raw = (_SQL_DIR / "0001_stage1.sql").read_text(encoding="utf-8")
    statements: list[str] = []
    buf: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buf).rstrip().rstrip(";"))
            buf = []
    if buf:
        statements.append("\n".join(buf).rstrip().rstrip(";"))
    return [item for item in statements if _TABLE_OBJECT.search(item)]


def _present_tables(conn: object) -> set[str]:
    result = conn.execute(  # type: ignore[attr-defined]
        text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n "
            "ON n.oid = c.relnamespace WHERE n.nspname = 'public' "
            "AND c.relname = ANY(:names)"
        ),
        {"names": list(_TABLES)},
    )
    return {str(row[0]) for row in result}  # type: ignore[attr-defined]


def upgrade() -> None:
    conn = op.get_bind()
    if _present_tables(conn) == set(_TABLES):
        # Fresh-database path: 0001's full-bundle replay already created
        # both tables; replaying again would raise DuplicateTableError.
        return
    for statement in _statements():
        conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS invariant_evaluations CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS domain_invariants CASCADE"))
