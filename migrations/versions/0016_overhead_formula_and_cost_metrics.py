"""Chapter 16.4 overhead formula completion + cost metrics (DDE-041).

Extends `control_plane_overhead_tasks` with the remaining Chapter 16.4
token-formula columns and creates `workload_class_cost_metrics` for
cost-per-verified-success tracking.

Idempotent: safe to replay onto a database already at 0015 (old overhead
columns) or onto a fresh database whose 0001 bundle already emits the
full current schema.
"""

from __future__ import annotations

import re
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"

_TABLES = ("workload_class_cost_metrics",)

_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("routing_tokens", "integer NOT NULL DEFAULT 0"),
    ("route_critic_tokens", "integer NOT NULL DEFAULT 0"),
    ("planning_tokens", "integer NOT NULL DEFAULT 0"),
    ("judge_tokens", "integer NOT NULL DEFAULT 0"),
    ("route_critic_invoked", "boolean NOT NULL DEFAULT false"),
    ("workload_class", "text NOT NULL DEFAULT 'unknown'"),
)

_TABLE_OBJECT = re.compile(
    rf"\b(?:TABLE|ON)\s+(?:{'|'.join(re.escape(name) for name in _TABLES)})\b",
    re.IGNORECASE,
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
    return [item for item in statements if _TABLE_OBJECT.search(item)]


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


def _column_present(conn: object, *, table: str, column: str) -> bool:
    result = conn.execute(  # type: ignore[attr-defined]
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table_name AND column_name = :column_name"
        ),
        {"table_name": table, "column_name": column},
    )
    return result.first() is not None  # type: ignore[attr-defined]


def _constraint_present(conn: object, *, name: str) -> bool:
    result = conn.execute(  # type: ignore[attr-defined]
        text("SELECT 1 FROM pg_constraint WHERE conname = :name"),
        {"name": name},
    )
    return result.first() is not None  # type: ignore[attr-defined]


def upgrade() -> None:
    conn = op.get_bind()

    for column, definition in _NEW_COLUMNS:
        if _column_present(conn, table="control_plane_overhead_tasks", column=column):
            continue
        conn.execute(
            text(
                f"ALTER TABLE control_plane_overhead_tasks "
                f"ADD COLUMN {column} {definition}"
            )
        )

    if not _constraint_present(
        conn, name="control_plane_overhead_tasks_worker_run_id_key"
    ):
        conn.execute(
            text(
                "ALTER TABLE control_plane_overhead_tasks "
                "ADD CONSTRAINT control_plane_overhead_tasks_worker_run_id_key "
                "UNIQUE (worker_run_id)"
            )
        )

    present = _present_tables(conn)
    for table in _TABLES:
        if table in present:
            continue
        for statement in _statements():
            conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS workload_class_cost_metrics CASCADE"))
    if _constraint_present(conn, name="control_plane_overhead_tasks_worker_run_id_key"):
        conn.execute(
            text(
                "ALTER TABLE control_plane_overhead_tasks "
                "DROP CONSTRAINT control_plane_overhead_tasks_worker_run_id_key"
            )
        )
    for column, _definition in reversed(_NEW_COLUMNS):
        conn.execute(
            text(
                f"ALTER TABLE control_plane_overhead_tasks "
                f"DROP COLUMN IF EXISTS {column}"
            )
        )
