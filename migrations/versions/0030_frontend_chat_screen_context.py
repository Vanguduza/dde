"""DDE-069 FrontendConversation current-screen context.

The canonical conversation model includes the current screen alongside candidate,
selection and viewport. Existing rows remain valid with NULL screen context.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        text(
            "ALTER TABLE frontend_conversations "
            "ADD COLUMN IF NOT EXISTS screen_key text"
        )
    )


def downgrade() -> None:
    op.get_bind().execute(
        text("ALTER TABLE frontend_conversations DROP COLUMN IF EXISTS screen_key")
    )
