"""Chapter 6.4 table (DDE-036) -- routing_simulation_runs.

Follows migration 0007's pattern exactly: replays the table's statements
from the canonical generated `schemas/sql/0001_stage1.sql` (the single
source of truth) rather than hand-authoring DDL a second time.
Idempotent: migration 0001, re-run against an empty database, already
creates this table from the regenerated bundle, so this migration
no-ops when it exists.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"

_TABLES = ("routing_simulation_runs",)


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
        text("SELECT to_regclass('public.routing_simulation_runs')")
    ).scalar()
    if exists is not None:
        return
    for statement in _statements():
        conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS routing_simulation_runs CASCADE"))
