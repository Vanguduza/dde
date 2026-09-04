"""DDE-069 design gateway and chat tables.

Follows migration 0025's pattern: replays these tables' statements from
the canonical generated `schemas/sql/0001_stage1.sql` rather than
hand-authoring DDL a second time. Idempotent: migration 0001, re-run
against an empty database, already creates them from the regenerated
bundle, so this migration no-ops when they exist.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"

_TABLES = (
    "design_sessions",
    "design_artifacts",
    "frontend_conversations",
    "frontend_conversation_turns",
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
    return [item for item in statements if any(name in item for name in _TABLES)]


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(text("SELECT to_regclass('public.design_sessions')")).scalar()
    if exists is not None:
        return
    for statement in _statements():
        conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    for table in reversed(_TABLES):
        conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
