"""Adoption #7 -- flaky_quarantines: durable flaky-check quarantine
markers.

Small and reversible by construction: one table, dropped wholesale on
downgrade. Uniqueness of "one active quarantine per (task_id,
check_ref)" is enforced by a PARTIAL unique index on ``lifted_at IS
NULL`` -- a plain UNIQUE constraint over ``lifted_at`` cannot do it,
because PostgreSQL treats NULLs as distinct and two active markers would
both satisfy it. Lifts stamp ``lifted_at``, so history rows accumulate
without blocking re-detection. Tenant/project RLS follows Chapter 3.2's
fail-closed GUC predicate, same shape as every stored table in
`schemas/sql/0001_stage1.sql`.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS flaky_quarantines (
    quarantine_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    check_ref text NOT NULL,
    detected_at timestamptz NOT NULL,
    lifted_at timestamptz,
    lifted_by text,
    sample_size integer NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (quarantine_id)
)
"""

_CREATE_PARTIAL_UNIQUE = """
CREATE UNIQUE INDEX IF NOT EXISTS flaky_quarantines_one_active_per_check
    ON flaky_quarantines (task_id, check_ref) WHERE lifted_at IS NULL
"""

_CREATE_ACTIVE_INDEX = """
CREATE INDEX IF NOT EXISTS ix_flaky_quarantines_task_active
    ON flaky_quarantines (task_id) WHERE lifted_at IS NULL
"""

_ENABLE_RLS = """
ALTER TABLE flaky_quarantines ENABLE ROW LEVEL SECURITY
"""

_FORCE_RLS = """
ALTER TABLE flaky_quarantines FORCE ROW LEVEL SECURITY
"""

_CREATE_POLICY = """
CREATE POLICY flaky_quarantines_tenant_isolation ON flaky_quarantines
    USING (
        tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid)
        AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)
    )
    WITH CHECK (
        tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid)
        AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)
    )
"""


def _policy_exists(conn: object) -> bool:
    result = conn.execute(  # type: ignore[attr-defined]
        text(
            "SELECT 1 FROM pg_policies WHERE policyname = "
            "'flaky_quarantines_tenant_isolation'"
        )
    )
    return result.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(_CREATE_TABLE))
    conn.execute(text(_CREATE_PARTIAL_UNIQUE))
    conn.execute(text(_CREATE_ACTIVE_INDEX))
    conn.execute(text(_ENABLE_RLS))
    conn.execute(text(_FORCE_RLS))
    if not _policy_exists(conn):
        conn.execute(text(_CREATE_POLICY))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "DROP POLICY IF EXISTS flaky_quarantines_tenant_isolation "
            "ON flaky_quarantines"
        )
    )
    conn.execute(text("DROP TABLE IF EXISTS flaky_quarantines CASCADE"))
