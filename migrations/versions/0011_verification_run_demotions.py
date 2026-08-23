"""EDR-0009 (accepted 2026-08-23) -- verification_run_demotions side-table.

Guardrail-demoted PARTIAL VerificationRuns previously left no durable trace:
Chapter 6.5's `routing_decision_outcomes.actual_verified_outcome` admits only
PASSED/FAILED and `RoutingTelemetryService.record_decision_outcome` gates on
terminal status, so a demoted run silently dropped out of decision-outcome
history. Per the accepted decision, this stays true -- the Chapter 6.5
schema is byte-stable by design -- and the demotion gains its own identity
in a small side-table keyed by `verification_run_id`, written by the same
guarded runner path that forces PARTIAL. Consumers join on
`verification_run_id` when they need to exclude or count the demoted
population.

One table, dropped wholesale on downgrade; unique per verification run (a
run demotes at most once -- terminal statuses are append-only). Tenant/
project RLS follows Chapter 3.2's fail-closed GUC predicate, same shape as
every stored table in `schemas/sql/0001_stage1.sql` and migration 0010.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS verification_run_demotions (
    demotion_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid NOT NULL,
    task_id uuid NOT NULL,
    worker_run_id uuid NOT NULL,
    verification_run_id uuid NOT NULL,
    source text NOT NULL,
    failure_class text NOT NULL,
    confidence numeric(5, 4) NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (demotion_id)
)
"""

_CREATE_UNIQUE = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_verification_run_demotions_run
    ON verification_run_demotions (verification_run_id)
"""

_CREATE_TASK_INDEX = """
CREATE INDEX IF NOT EXISTS ix_verification_run_demotions_task
    ON verification_run_demotions (task_id)
"""

_ENABLE_RLS = """
ALTER TABLE verification_run_demotions ENABLE ROW LEVEL SECURITY
"""

_FORCE_RLS = """
ALTER TABLE verification_run_demotions FORCE ROW LEVEL SECURITY
"""

_CREATE_POLICY = """
CREATE POLICY verification_run_demotions_tenant_isolation
    ON verification_run_demotions
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
            "'verification_run_demotions_tenant_isolation'"
        )
    )
    return result.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(_CREATE_TABLE))
    conn.execute(text(_CREATE_UNIQUE))
    conn.execute(text(_CREATE_TASK_INDEX))
    conn.execute(text(_ENABLE_RLS))
    conn.execute(text(_FORCE_RLS))
    if not _policy_exists(conn):
        conn.execute(text(_CREATE_POLICY))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "DROP POLICY IF EXISTS verification_run_demotions_tenant_isolation "
            "ON verification_run_demotions"
        )
    )
    conn.execute(text("DROP TABLE IF EXISTS verification_run_demotions CASCADE"))
