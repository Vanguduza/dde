"""Captured provider credentials + broker-private vault (static-secret capture).

Depends on 0016 so this revision lands without the DDE-046 donor-lab chain.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0018"
down_revision = "0016"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[2] / "schemas" / "sql"
_TABLES = ("captured_provider_credentials",)

_VAULT_SQL = """
CREATE TABLE IF NOT EXISTS broker_static_secret_material (
    capture_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    provider_id text NOT NULL,
    secret_value text NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (capture_id)
);
ALTER TABLE broker_static_secret_material ENABLE ROW LEVEL SECURITY;
ALTER TABLE broker_static_secret_material FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS broker_static_secret_material_tenant_isolation
    ON broker_static_secret_material;
CREATE POLICY broker_static_secret_material_tenant_isolation
    ON broker_static_secret_material
    USING (
        tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid)
        AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)
    )
    WITH CHECK (
        tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid)
        AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)
    );
"""


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
    if _present_tables(conn) != set(_TABLES):
        for statement in _statements():
            conn.execute(text(statement))
    for statement in _VAULT_SQL.strip().split(";"):
        cleaned = statement.strip()
        if cleaned:
            conn.execute(text(cleaned))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS broker_static_secret_material CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS captured_provider_credentials CASCADE"))
