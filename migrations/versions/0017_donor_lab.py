"""Donor Lab tables (DDE-046 / Chapter 13.8) -- donor_artifacts and
feature_dna.

Replays statements for the two new tables from the canonical generated
`schemas/sql/0001_stage1.sql` (migration 0012's pattern). Tenant/project
RLS follows Chapter 3.2. Idempotent on a fresh database whose 0001
bundle already emits both tables.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"

_TABLES = ("donor_artifacts", "feature_dna")


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
        return
    for statement in _statements():
        conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS feature_dna CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS donor_artifacts CASCADE"))
