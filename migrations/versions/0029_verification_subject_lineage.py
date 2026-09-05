"""Widen VerificationRun lineage for Frontend candidate revisions.

AD-036 / Frontend Studio Rev 3 section 20.1 requires candidate revisions to
produce ordinary VerificationRun/Evidence rather than a parallel verifier.
Blueprint Rev 3 section 17.1 already defines verification lineage as
task/change-packet + revision, so worker lineage remains valid but is not the
only legal subject.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text("ALTER TABLE verification_runs ALTER COLUMN task_attempt_id DROP NOT NULL")
    )
    conn.execute(
        text("ALTER TABLE verification_runs ALTER COLUMN worker_run_id DROP NOT NULL")
    )
    conn.execute(
        text("ALTER TABLE verification_runs ADD COLUMN IF NOT EXISTS subject_kind text")
    )
    conn.execute(
        text("ALTER TABLE verification_runs ADD COLUMN IF NOT EXISTS subject_id uuid")
    )
    conn.execute(
        text(
            "UPDATE verification_runs SET subject_kind = 'WORKER_RUN', "
            "subject_id = worker_run_id WHERE subject_kind IS NULL AND "
            "worker_run_id IS NOT NULL"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE verification_runs ADD CONSTRAINT "
            "verification_runs_subject_pair CHECK "
            "((subject_kind IS NULL AND subject_id IS NULL) OR "
            "(subject_kind IS NOT NULL AND subject_id IS NOT NULL))"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE verification_runs ADD CONSTRAINT "
            "verification_runs_subject_kind_known CHECK "
            "(subject_kind IS NULL OR subject_kind IN "
            "('WORKER_RUN', 'FRONTEND_CANDIDATE'))"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE verification_runs ADD CONSTRAINT "
            "verification_runs_subject_sequence_key UNIQUE "
            "(subject_kind, subject_id, sequence)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    non_worker = conn.execute(
        text(
            "SELECT count(*) FROM verification_runs WHERE "
            "worker_run_id IS NULL OR task_attempt_id IS NULL"
        )
    ).scalar_one()
    if int(non_worker) > 0:
        raise RuntimeError(
            "cannot downgrade verification subject lineage while non-worker "
            "VerificationRun rows exist; preserve evidence or migrate it first"
        )
    conn.execute(
        text(
            "ALTER TABLE verification_runs DROP CONSTRAINT IF EXISTS "
            "verification_runs_subject_sequence_key"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE verification_runs DROP CONSTRAINT IF EXISTS "
            "verification_runs_subject_kind_known"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE verification_runs DROP CONSTRAINT IF EXISTS "
            "verification_runs_subject_pair"
        )
    )
    conn.execute(text("ALTER TABLE verification_runs DROP COLUMN IF EXISTS subject_id"))
    conn.execute(
        text("ALTER TABLE verification_runs DROP COLUMN IF EXISTS subject_kind")
    )
    conn.execute(
        text("ALTER TABLE verification_runs ALTER COLUMN worker_run_id SET NOT NULL")
    )
    conn.execute(
        text("ALTER TABLE verification_runs ALTER COLUMN task_attempt_id SET NOT NULL")
    )
