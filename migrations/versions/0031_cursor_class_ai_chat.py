"""DDE-069 Cursor-class AI Chat persistence.

Extends the existing FrontendConversation control plane with durable mode,
model/workspace/plan/branch context and adds attachments, plans, activity,
conversation checkpoints and change-review records. Attachment bytes are not
stored in PostgreSQL; only scoped content-addressed metadata is persisted.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

_SCOPE_POLICY = (
    "tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid) "
    "AND project_id = CAST(current_setting('dde.project_id', true) AS uuid)"
)


def _rls(table: str) -> None:
    op.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        text(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            f"USING ({_SCOPE_POLICY}) WITH CHECK ({_SCOPE_POLICY})"
        )
    )


def upgrade() -> None:
    # Migration 0001 intentionally replays the current generated schema bundle.
    # On a fresh database that bundle already contains the Cursor-class Chat
    # tables/columns, so this historical additive migration must no-op rather
    # than attempt to add them twice. Historical databases at 0030 do not have
    # this marker table and still execute the original upgrade path.
    conn = op.get_bind()
    if (
        conn.execute(
            text("SELECT to_regclass('public.frontend_chat_attachments')")
        ).scalar()
        is not None
    ):
        return
    op.execute(text("ALTER TABLE frontend_conversations ADD COLUMN title text"))
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD COLUMN status text "
            "NOT NULL DEFAULT 'OPEN'"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD COLUMN mode text "
            "NOT NULL DEFAULT 'ASK'"
        )
    )
    op.execute(
        text("ALTER TABLE frontend_conversations ADD COLUMN model_profile_id text")
    )
    op.execute(
        text("ALTER TABLE frontend_conversations ADD COLUMN active_workspace_id uuid")
    )
    op.execute(
        text("ALTER TABLE frontend_conversations ADD COLUMN active_plan_id uuid")
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD COLUMN parent_conversation_id uuid"
        )
    )
    op.execute(
        text("ALTER TABLE frontend_conversations ADD COLUMN branched_from_turn_id uuid")
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD COLUMN pinned_context_refs jsonb "
            "NOT NULL DEFAULT '[]'::jsonb"
        )
    )
    op.execute(text("ALTER TABLE frontend_conversations ADD COLUMN created_by uuid"))
    op.execute(
        text("ALTER TABLE frontend_conversations ADD COLUMN archived_at timestamptz")
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD CONSTRAINT "
            "frontend_conversations_status_known "
            "CHECK (status IN ('OPEN','ARCHIVED'))"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD CONSTRAINT "
            "frontend_conversations_mode_known "
            "CHECK (mode IN ('ASK','PLAN','EXECUTE'))"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD CONSTRAINT "
            "frontend_conversations_active_workspace_id_fkey "
            "FOREIGN KEY (active_workspace_id) REFERENCES workspaces(workspace_id)"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD CONSTRAINT "
            "frontend_conversations_parent_conversation_id_fkey "
            "FOREIGN KEY (parent_conversation_id) "
            "REFERENCES frontend_conversations(conversation_id)"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD CONSTRAINT "
            "frontend_conversations_branched_from_turn_id_fkey "
            "FOREIGN KEY (branched_from_turn_id) "
            "REFERENCES frontend_conversation_turns(turn_id)"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD CONSTRAINT "
            "frontend_conversations_created_by_fkey "
            "FOREIGN KEY (created_by) REFERENCES principals(principal_id)"
        )
    )

    op.execute(
        text(
            "ALTER TABLE frontend_conversation_turns ADD COLUMN attachment_ids jsonb "
            "NOT NULL DEFAULT '[]'::jsonb"
        )
    )
    op.execute(text("ALTER TABLE frontend_conversation_turns ADD COLUMN plan_id uuid"))
    op.execute(
        text("ALTER TABLE frontend_conversation_turns ADD COLUMN model_profile_id text")
    )

    op.execute(
        text(
            """
CREATE TABLE frontend_chat_attachments (
    attachment_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(tenant_id),
    project_id uuid NOT NULL REFERENCES projects(project_id),
    conversation_id uuid NOT NULL REFERENCES frontend_conversations(conversation_id),
    turn_id uuid REFERENCES frontend_conversation_turns(turn_id),
    source_kind text NOT NULL,
    filename text NOT NULL,
    media_type text NOT NULL,
    size_bytes integer NOT NULL CHECK (size_bytes >= 0),
    content_hash text,
    storage_key text,
    workspace_path text,
    extraction_state text NOT NULL CHECK (
        extraction_state IN ('PENDING','EXTRACTED','UNSUPPORTED','FAILED')
    ),
    extracted_text text,
    status text NOT NULL CHECK (
        status IN ('RESERVED','ACTIVE','REMOVED','QUARANTINED')
    ),
    created_by uuid REFERENCES principals(principal_id),
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    UNIQUE (conversation_id, attachment_id)
)
"""
        )
    )
    op.execute(
        text(
            """
CREATE TABLE frontend_chat_plans (
    plan_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(tenant_id),
    project_id uuid NOT NULL REFERENCES projects(project_id),
    mission_id uuid NOT NULL REFERENCES missions(mission_id),
    conversation_id uuid NOT NULL REFERENCES frontend_conversations(conversation_id),
    title text NOT NULL,
    objective text NOT NULL,
    state text NOT NULL CHECK (
        state IN ('DRAFT','READY','APPROVED','EXECUTING','PAUSED',
        'COMPLETED','FAILED','CANCELLED')
    ),
    approval_required boolean NOT NULL,
    approved_by uuid REFERENCES principals(principal_id),
    approved_at timestamptz,
    steps jsonb NOT NULL DEFAULT '[]'::jsonb,
    active_step_id uuid,
    workspace_id uuid REFERENCES workspaces(workspace_id),
    task_graph_id uuid REFERENCES task_graphs(graph_id),
    created_from_turn_id uuid REFERENCES frontend_conversation_turns(turn_id),
    context_snapshot jsonb,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
)
"""
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations ADD CONSTRAINT "
            "frontend_conversations_active_plan_id_fkey "
            "FOREIGN KEY (active_plan_id) REFERENCES frontend_chat_plans(plan_id)"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversation_turns ADD CONSTRAINT "
            "frontend_conversation_turns_plan_id_fkey "
            "FOREIGN KEY (plan_id) REFERENCES frontend_chat_plans(plan_id)"
        )
    )
    op.execute(
        text(
            """
CREATE TABLE frontend_chat_activities (
    activity_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(tenant_id),
    project_id uuid NOT NULL REFERENCES projects(project_id),
    conversation_id uuid NOT NULL REFERENCES frontend_conversations(conversation_id),
    sequence integer NOT NULL CHECK (sequence >= 1),
    turn_id uuid REFERENCES frontend_conversation_turns(turn_id),
    plan_id uuid REFERENCES frontend_chat_plans(plan_id),
    workspace_id uuid REFERENCES workspaces(workspace_id),
    command_id uuid REFERENCES command_idempotency(command_id),
    kind text NOT NULL,
    state text NOT NULL,
    label text NOT NULL,
    detail text,
    refs jsonb NOT NULL DEFAULT '{}'::jsonb,
    cancellable boolean NOT NULL,
    cancel_reason text,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    UNIQUE (conversation_id, sequence)
)
"""
        )
    )
    op.execute(
        text(
            """
CREATE TABLE frontend_chat_checkpoints (
    checkpoint_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(tenant_id),
    project_id uuid NOT NULL REFERENCES projects(project_id),
    conversation_id uuid NOT NULL REFERENCES frontend_conversations(conversation_id),
    turn_sequence integer NOT NULL,
    mode text NOT NULL,
    model_profile_id text,
    plan_id uuid REFERENCES frontend_chat_plans(plan_id),
    workspace_id uuid REFERENCES workspaces(workspace_id),
    pinned_context_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    attachment_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    workspace_revision text,
    diff_hash text,
    context_hash text NOT NULL,
    note text,
    created_by uuid REFERENCES principals(principal_id),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
)
"""
        )
    )
    op.execute(
        text(
            """
CREATE TABLE frontend_chat_change_reviews (
    review_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(tenant_id),
    project_id uuid NOT NULL REFERENCES projects(project_id),
    conversation_id uuid NOT NULL REFERENCES frontend_conversations(conversation_id),
    workspace_id uuid NOT NULL REFERENCES workspaces(workspace_id),
    path text NOT NULL,
    base_revision text,
    workspace_revision text,
    diff_hash text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('PENDING','ACCEPTED','REVERTED')),
    reviewed_by uuid REFERENCES principals(principal_id),
    reviewed_at timestamptz,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    UNIQUE (conversation_id, workspace_id, path, diff_hash)
)
"""
        )
    )

    for table in (
        "frontend_chat_attachments",
        "frontend_chat_plans",
        "frontend_chat_activities",
        "frontend_chat_checkpoints",
        "frontend_chat_change_reviews",
    ):
        _rls(table)

    op.execute(
        text(
            "CREATE INDEX frontend_conversations_mission_history_idx "
            "ON frontend_conversations (mission_id, status, updated_at DESC)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX frontend_chat_attachments_conversation_idx "
            "ON frontend_chat_attachments (conversation_id, status, created_at)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX frontend_chat_plans_conversation_idx "
            "ON frontend_chat_plans (conversation_id, updated_at DESC)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX frontend_chat_activities_conversation_idx "
            "ON frontend_chat_activities (conversation_id, sequence)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX frontend_chat_checkpoints_conversation_idx "
            "ON frontend_chat_checkpoints (conversation_id, created_at DESC)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX frontend_chat_change_reviews_workspace_idx "
            "ON frontend_chat_change_reviews (workspace_id, path, updated_at DESC)"
        )
    )


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS frontend_chat_change_reviews_workspace_idx"))
    op.execute(text("DROP INDEX IF EXISTS frontend_chat_checkpoints_conversation_idx"))
    op.execute(text("DROP INDEX IF EXISTS frontend_chat_activities_conversation_idx"))
    op.execute(text("DROP INDEX IF EXISTS frontend_chat_plans_conversation_idx"))
    op.execute(text("DROP INDEX IF EXISTS frontend_chat_attachments_conversation_idx"))
    op.execute(text("DROP INDEX IF EXISTS frontend_conversations_mission_history_idx"))
    op.execute(
        text(
            "ALTER TABLE frontend_conversation_turns DROP CONSTRAINT IF EXISTS "
            "frontend_conversation_turns_plan_id_fkey"
        )
    )
    op.execute(
        text(
            "ALTER TABLE frontend_conversations DROP CONSTRAINT IF EXISTS "
            "frontend_conversations_active_plan_id_fkey"
        )
    )
    for table in (
        "frontend_chat_change_reviews",
        "frontend_chat_checkpoints",
        "frontend_chat_activities",
        "frontend_chat_plans",
        "frontend_chat_attachments",
    ):
        op.execute(text(f"DROP TABLE IF EXISTS {table}"))
    for constraint in (
        "frontend_conversations_created_by_fkey",
        "frontend_conversations_branched_from_turn_id_fkey",
        "frontend_conversations_parent_conversation_id_fkey",
        "frontend_conversations_active_workspace_id_fkey",
        "frontend_conversations_mode_known",
        "frontend_conversations_status_known",
    ):
        op.execute(
            text(
                "ALTER TABLE frontend_conversations DROP CONSTRAINT IF EXISTS "
                + constraint
            )
        )
    for column in ("model_profile_id", "plan_id", "attachment_ids"):
        op.execute(
            text(
                "ALTER TABLE frontend_conversation_turns DROP COLUMN IF EXISTS "
                + column
            )
        )
    for column in (
        "archived_at",
        "created_by",
        "pinned_context_refs",
        "branched_from_turn_id",
        "parent_conversation_id",
        "active_plan_id",
        "active_workspace_id",
        "model_profile_id",
        "mode",
        "status",
        "title",
    ):
        op.execute(
            text("ALTER TABLE frontend_conversations DROP COLUMN IF EXISTS " + column)
        )
