"""Chapter 11.6 tables (DDE-038) -- seed_datasets and
product_environments.

Replays the statements for the two new tables from the canonical
generated `schemas/sql/0001_stage1.sql` (migration 0009's pattern), so
the schema bundle stays the single source of truth. One downgrade drops
both tables wholesale. Tenant/project RLS follows Chapter 3.2's
fail-closed GUC predicate, same shape as every stored table.

Idempotent exactly like 0009: the bundle 0001 replays on a fresh
database ALREADY emits both tables (they live in the generated SQL), so
this migration no-ops when they exist and only forward-applies onto a
database stopped at 0011 or earlier.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"

_TABLES = ("seed_datasets", "product_environments")


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
    return [item for item in statements if any(name in item for name in _TABLES)]


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
    conn.execute(text("DROP TABLE IF EXISTS product_environments CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS seed_datasets CASCADE"))
