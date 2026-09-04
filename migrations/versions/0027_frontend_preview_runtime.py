"""DDE-069 code-backed frontend preview sessions."""

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
    buf: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            statement = "\n".join(buf).rstrip().rstrip(";")
            if _TABLE in statement:
                statements.append(statement)
            buf = []
    return statements


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(text(f"SELECT to_regclass('public.{_TABLE}')")).scalar()
    if exists is not None:
        return
    for statement in _statements():
        conn.execute(text(statement))


def downgrade() -> None:
    op.get_bind().execute(text(f"DROP TABLE IF EXISTS {_TABLE} CASCADE"))
