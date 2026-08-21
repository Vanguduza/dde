"""Chapter 5.10 tables (DDE-033) -- asserted_edges and derived_edges.

Follows migration 0004's pattern exactly: replays the two tables'
statements from the canonical generated `schemas/sql/0001_stage1.sql` (the
single source of truth) rather than hand-authoring DDL a second time.
Idempotent: migration 0001, re-run against an empty database, already
creates these tables from the regenerated bundle, so this migration
no-ops when they exist.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"

_TABLES = ("asserted_edges", "derived_edges")


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


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(text("SELECT to_regclass('public.asserted_edges')")).scalar()
    if exists is not None:
        return
    for statement in _statements():
        conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS derived_edges CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS asserted_edges CASCADE"))
