"""Chapter 11.3 tables (DDE-037) -- mission_oracle_evaluations and
nullable acceptance_oracles.task_id.

Follows migration 0008's pattern for the new table: replays statements
from the canonical generated `schemas/sql/0001_stage1.sql`. Also drops
NOT NULL on `acceptance_oracles.task_id` so a mission-scope oracle can
exist without a fabricated task identity. Idempotent: 0001 against an
empty database already emits both shapes, so this migration no-ops the
pieces that already exist.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"

_TABLES = ("mission_oracle_evaluations",)


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
    conn.execute(
        text("ALTER TABLE acceptance_oracles ALTER COLUMN task_id DROP NOT NULL")
    )
    exists = conn.execute(
        text("SELECT to_regclass('public.mission_oracle_evaluations')")
    ).scalar()
    if exists is not None:
        return
    for statement in _statements():
        conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS mission_oracle_evaluations CASCADE"))
    conn.execute(text("DELETE FROM acceptance_oracles WHERE task_id IS NULL"))
    conn.execute(
        text("ALTER TABLE acceptance_oracles ALTER COLUMN task_id SET NOT NULL")
    )
