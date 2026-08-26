"""Chapter 5.13 tables (DDE-059) -- context_activation_state.

Follows migration 0022's pattern: replays the table's statements from
the canonical generated `schemas/sql/0001_stage1.sql`. Idempotent:
migration 0001 against an empty database already creates this table
from the regenerated bundle, so this migration no-ops when it exists.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"

_TABLES = ("context_activation_state",)


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
    exists = conn.execute(
        text("SELECT to_regclass('public.context_activation_state')")
    ).scalar()
    if exists is not None:
        return
    for statement in _statements():
        conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS context_activation_state CASCADE"))
