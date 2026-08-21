"""Semantic context index tables (Chapter 5.4) — context_indexes and context_chunks.

Stage 1 shipped the context_packages table but deferred the index lifecycle.
This migration adds the two tables Chapter 5.4 requires, by replaying exactly
the `context_indexes` / `context_chunks` statements from the canonical
generated `schemas/sql/0001_stage1.sql` (the single source of truth). It is
idempotent: migration 0001, when re-run against an empty database, already
creates these tables from the regenerated bundle, so this migration no-ops
when they exist.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"

#: Every generated statement for these two tables mentions the table name at
#: least once, so a substring filter over the canonical bundle yields exactly
#: the CREATE TABLE / FOREIGN KEY / ENABLE / FORCE / CREATE POLICY statements.
_TABLES = ("context_indexes", "context_chunks")


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
    exists = conn.execute(text("SELECT to_regclass('public.context_chunks')")).scalar()
    if exists is not None:
        return
    for statement in _statements():
        conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS context_chunks CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS context_indexes CASCADE"))
