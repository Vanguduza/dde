"""Donor taint table + feature_dna.taint_tags (DDE-047 / Chapter 13.8).

Depends on 0018. Fresh databases whose 0001 bundle already emits
donor_taints and taint_tags are no-ops for those statements.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"


def _statements_for(names: tuple[str, ...]) -> list[str]:
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
    return [item for item in statements if any(name in item for name in names)]


def upgrade() -> None:
    conn = op.get_bind()
    # feature_dna.taint_tags may be missing on DBs created via 0017.
    has_col = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'feature_dna' "
            "AND column_name = 'taint_tags'"
        )
    ).first()
    if has_col is None:
        conn.execute(
            text(
                "ALTER TABLE feature_dna "
                "ADD COLUMN taint_tags jsonb NOT NULL DEFAULT '[]'::jsonb"
            )
        )

    present = conn.execute(
        text(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n "
            "ON n.oid = c.relnamespace WHERE n.nspname = 'public' "
            "AND c.relname = 'donor_taints'"
        )
    ).first()
    if present is not None:
        return
    for statement in _statements_for(("donor_taints",)):
        conn.execute(text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS donor_taints CASCADE"))
    # Leave taint_tags in place on downgrade of a column that may hold
    # data; dropping it is irreversible for Feature DNA rows.
