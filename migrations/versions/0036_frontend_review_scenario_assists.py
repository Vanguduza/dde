"""DDE-069 review comments, preview scenarios, and editor-assist policy."""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None
_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"
_TABLES = (
    "design_comments",
    "frontend_preview_scenarios",
    "frontend_editor_assist_states",
    "frontend_attention_acknowledgements",
)


def _existing_tables() -> set[str]:
    conn = op.get_bind()
    return {
        table
        for table in _TABLES
        if conn.execute(
            text("SELECT to_regclass(:name)"), {"name": f"public.{table}"}
        ).scalar()
        is not None
    }


def _statements() -> list[str]:
    raw = (_SQL_DIR / "0001_stage1.sql").read_text(encoding="utf-8")
    statements = []
    buf = []
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
    existing = _existing_tables()
    if existing == set(_TABLES):
        return
    if existing:
        raise RuntimeError(
            "partial 0036 schema already exists: " + ", ".join(sorted(existing))
        )
    conn = op.get_bind()
    for statement in _statements():
        conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    for table in reversed(_TABLES):
        conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
