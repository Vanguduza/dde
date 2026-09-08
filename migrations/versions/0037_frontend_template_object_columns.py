"""Restore canonical Source Intelligence template object-store columns.

Revision 0034 always declared these nullable columns, but regenerated Stage-1 SQL
briefly omitted them while 0034's fresh-schema guard returned early. This repair is
idempotent: old incremental databases already containing the 0034 columns remain
unchanged, while affected fresh installations gain the missing canonical columns.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None

_COLUMNS = (
    ("content_object_ref", "text"),
    ("content_object_backend", "text"),
    ("content_size_bytes", "integer"),
)


def upgrade() -> None:
    conn = op.get_bind()
    for name, sql_type in _COLUMNS:
        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='frontend_templates' "
                "AND column_name=:name"
            ),
            {"name": name},
        ).first()
        if exists is None:
            conn.execute(
                sa.text(f"ALTER TABLE frontend_templates ADD COLUMN {name} {sql_type}")
            )


def downgrade() -> None:
    # No-op by design. These columns belong to canonical 0034 Source Intelligence;
    # 0037 only repairs databases where the regenerated 0001 bundle omitted them.
    # 0034's own downgrade removes the table at the correct historical boundary.
    return
