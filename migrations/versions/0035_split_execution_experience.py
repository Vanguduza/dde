# ruff: noqa: E501
"""Split DDE-069 execution experience from DDE-057 routing learning.

The Universal DDE Chat tranche reused ``experience_records`` for Blueprint
§6.3 full worker-configuration history. DDE-057 already owns that table for
Chapter 6.8 routing-learning eligibility. Both contracts are authoritative.
This migration preserves both without discarding either data model.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

_SCOPE_POLICY = (
    "tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) "
    "AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)"
)


def _exists(table: str) -> bool:
    conn = op.get_bind()
    return (
        conn.execute(
            text("SELECT to_regclass(:name)"), {"name": f"public.{table}"}
        ).scalar()
        is not None
    )


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    return bool(
        conn.execute(
            text(
                "SELECT EXISTS ("
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:table "
                "AND column_name=:column)"
            ),
            {"table": table, "column": column},
        ).scalar()
    )


def _enable_rls(table: str) -> None:
    op.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        text(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            f"USING ({_SCOPE_POLICY}) WITH CHECK ({_SCOPE_POLICY})"
        )
    )


def _create_execution_table(table: str) -> None:
    op.execute(
        text(
            f"""CREATE TABLE {table} (
    experience_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    task_id uuid,
    worker_run_id uuid,
    worker_session_id uuid,
    task_signature jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    worker_configuration jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    outcome jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    economics jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    failure_signatures jsonb NOT NULL DEFAULT '[]'::jsonb,
    verification_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    authority_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (experience_id)
)"""
        )
    )
    refs = (
        ("tenant_id", "tenants", "tenant_id"),
        ("project_id", "projects", "project_id"),
        ("mission_id", "missions", "mission_id"),
        ("task_id", "tasks", "task_id"),
        ("worker_run_id", "worker_runs", "run_id"),
        ("worker_session_id", "worker_sessions", "worker_session_id"),
    )
    for column, ref_table, ref_column in refs:
        op.execute(
            text(
                f"ALTER TABLE {table} ADD CONSTRAINT {table}_{column}_fkey "
                f"FOREIGN KEY ({column}) REFERENCES {ref_table} ({ref_column})"
            )
        )
    _enable_rls(table)


def _create_learning_table() -> None:
    op.execute(
        text(
            """CREATE TABLE experience_records (
    experience_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mission_id uuid,
    task_id uuid,
    route_decision_id uuid,
    task_attempt_id uuid,
    verification_run_id uuid,
    routing_simulation_run_id uuid,
    outcome_id uuid,
    experience_origin text NOT NULL,
    routing_policy_version text NOT NULL,
    candidate_set_hash text NOT NULL,
    selection_propensity numeric NOT NULL,
    prediction_vector jsonb NOT NULL DEFAULT '{}'::jsonb,
    observed_outcome_vector jsonb NOT NULL DEFAULT '{}'::jsonb,
    verification_confidence numeric NOT NULL,
    failure_attribution text NOT NULL,
    attribution_confidence numeric NOT NULL,
    holdout_partition text NOT NULL,
    promotion_evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    drift_snapshot_id uuid,
    learning_run_id uuid,
    eligible_for_routing_training boolean NOT NULL,
    eligibility_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
    down_weighted boolean NOT NULL,
    promotion_state text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (experience_id),
    UNIQUE (verification_run_id),
    UNIQUE (routing_simulation_run_id),
    CHECK ((experience_origin <> 'simulation' OR eligible_for_routing_training = false)),
    CHECK (((experience_origin = 'real' AND verification_run_id IS NOT NULL) OR (experience_origin = 'simulation' AND routing_simulation_run_id IS NOT NULL)))
)"""
        )
    )
    refs = (
        ("tenant_id", "tenants", "tenant_id"),
        ("project_id", "projects", "project_id"),
        ("route_decision_id", "route_decisions", "decision_id"),
        ("verification_run_id", "verification_runs", "verification_run_id"),
        ("routing_simulation_run_id", "routing_simulation_runs", "run_id"),
        ("outcome_id", "routing_decision_outcomes", "outcome_id"),
    )
    for column, ref_table, ref_column in refs:
        op.execute(
            text(
                "ALTER TABLE experience_records ADD CONSTRAINT "
                f"experience_records_{column}_fkey FOREIGN KEY ({column}) "
                f"REFERENCES {ref_table} ({ref_column})"
            )
        )
    _enable_rls("experience_records")


_EXECUTION_COLUMNS = (
    "experience_id, tenant_id, project_id, mission_id, task_id, worker_run_id, "
    "worker_session_id, task_signature, worker_configuration, outcome, economics, "
    "failure_signatures, verification_refs, authority_refs, created_at, updated_at"
)


def upgrade() -> None:
    old_exists = _exists("experience_records")
    execution_exists = _exists("execution_experience_records")
    old_is_execution = old_exists and _has_column(
        "experience_records", "task_signature"
    )
    old_is_learning = old_exists and _has_column(
        "experience_records", "experience_origin"
    )

    if old_is_execution and old_is_learning:
        raise RuntimeError(
            "experience_records has conflicting execution and learning shapes"
        )
    if old_is_execution:
        if execution_exists:
            raise RuntimeError(
                "both collided and split execution experience tables exist"
            )
        _create_execution_table("execution_experience_records")
        op.execute(
            text(
                f"INSERT INTO execution_experience_records ({_EXECUTION_COLUMNS}) "
                f"SELECT {_EXECUTION_COLUMNS} FROM experience_records"
            )
        )
        op.execute(text("DROP TABLE experience_records"))
        _create_learning_table()
        return

    if not old_exists:
        _create_learning_table()
    elif not old_is_learning:
        raise RuntimeError("experience_records has an unrecognized schema")

    if not execution_exists:
        _create_execution_table("execution_experience_records")


def downgrade() -> None:
    """Return to the *current* canonical 0034 schema without reintroducing the collision.

    This revision is a compatibility repair for databases that reached historical 0034
    while ``0032`` still reused ``experience_records``. The current migration history
    corrects 0021/0032 so canonical 0034 already owns two distinct tables. Downgrading
    0035 must therefore preserve that split. Recreating the collided table would produce
    a schema that no current 0034 migration describes and would also break downgrade-to-
    base because the collided worker-session foreign key outlives revision 0032.
    """
    if not _exists("experience_records") or not _has_column(
        "experience_records", "experience_origin"
    ):
        raise RuntimeError(
            "cannot downgrade 0035: routing-learning experience_records is missing "
            "or has a non-canonical shape"
        )
    if not _exists("execution_experience_records") or not _has_column(
        "execution_experience_records", "task_signature"
    ):
        raise RuntimeError(
            "cannot downgrade 0035: execution_experience_records is missing "
            "or has a non-canonical shape"
        )
