"""Chapter 6.9 tables (DDE-058) -- learned_routing_policies and
routing_activation_state.

Follows migration 0021's pattern: replays the tables' statements from
the canonical generated `schemas/sql/0001_stage1.sql`. Idempotent:
migration 0001 against an empty database already creates these tables
from the regenerated bundle, so this migration no-ops when they exist.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"

_TABLES = ("learned_routing_policies", "routing_activation_state")


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
        text("SELECT to_regclass('public.learned_routing_policies')")
    ).scalar()
    if exists is not None:
        return
    for statement in _statements():
        conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS routing_activation_state CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS learned_routing_policies CASCADE"))
