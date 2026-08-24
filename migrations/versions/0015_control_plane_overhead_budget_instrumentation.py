"""Chapter 16.4 control-plane overhead instrumentation (DDE-041).

Adds `context_packages.assembly_tokens` (required for overhead token
instrumentation) and creates the durable Chapter 16.4 tables:

- `control_plane_overhead_tasks`
- `tenant_overhead_budget_settings`

Idempotent: safe to replay onto a partially-migrated schema.
"""

from __future__ import annotations

import re
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"

_TABLES = ("control_plane_overhead_tasks", "tenant_overhead_budget_settings")


def _statements_for(table: str) -> list[str]:
    raw = (_SQL_DIR / "0001_stage1.sql").read_text(encoding="utf-8")
    buf: list[str] = []
    statements: list[str] = []
    pattern = re.compile(rf"\b(?:TABLE|ON)\s+{re.escape(table)}\b", re.IGNORECASE)
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            candidate = "\n".join(buf).rstrip().rstrip(";")
            if pattern.search(candidate):
                statements.append(candidate)
            buf = []
    if buf:
        candidate = "\n".join(buf).rstrip().rstrip(";")
        if pattern.search(candidate):
            statements.append(candidate)
    return statements


def _present_tables(conn: object) -> set[str]:
    result = conn.execute(  # type: ignore[attr-defined]
        text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n "
            "ON n.oid = c.relnamespace WHERE n.nspname = 'public' "
            "AND c.relname = ANY(:names)"
        ),
        {"names": list(_TABLES)},
    )
    return {str(row[0]) for row in result}  # type: ignore[attr-defined]


def upgrade() -> None:
    conn = op.get_bind()

    col = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'context_packages' AND column_name = 'assembly_tokens'"
        )
    ).first()
    if col is None:
        conn.execute(
            text(
                "ALTER TABLE context_packages "
                "ADD COLUMN assembly_tokens integer NOT NULL DEFAULT 0"
            )
        )

    present = _present_tables(conn)
    for table in _TABLES:
        if table in present:
            continue
        for statement in _statements_for(table):
            conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS control_plane_overhead_tasks CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS tenant_overhead_budget_settings CASCADE"))
    conn.execute(
        text("ALTER TABLE context_packages DROP COLUMN IF EXISTS assembly_tokens")
    )
