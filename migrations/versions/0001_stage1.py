"""Stage 1 tables from Chapter 3.3."""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"


def _statements(filename: str) -> list[str]:
    raw = (_SQL_DIR / filename).read_text(encoding="utf-8")
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
    return [item for item in statements if item]


def upgrade() -> None:
    conn = op.get_bind()
    for statement in _statements("0001_stage1.sql"):
        conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    for statement in _statements("0001_stage1_down.sql"):
        conn.execute(text(statement))
