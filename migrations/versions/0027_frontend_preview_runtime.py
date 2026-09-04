"""DDE-069 durable candidate preview sessions.

Replays the schema-owned table statement from the generated Stage 1 bundle.
Migration 0001 already creates it for a new database; this revision upgrades
existing DDE-069 installations without maintaining a second DDL definition.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"
_TABLE = "frontend_preview_sessions"


def _statements() -> list[str]:
    raw = (_SQL_DIR / "0001_stage1.sql").read_text(encoding="utf-8")
    statements: list[str] = []
    buffer: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buffer).rstrip().rstrip(";"))
            buffer = []
    if buffer:
        statements.append("\n".join(buffer).rstrip().rstrip(";"))
    return [statement for statement in statements if _TABLE in statement]


def upgrade() -> None:
    connection = op.get_bind()
    exists = connection.execute(
        text("SELECT to_regclass('public.frontend_preview_sessions')")
    ).scalar()
    if exists is not None:
        return
    for statement in _statements():
        connection.execute(text(statement))


def downgrade() -> None:
    op.get_bind().execute(text(f"DROP TABLE IF EXISTS {_TABLE} CASCADE"))
