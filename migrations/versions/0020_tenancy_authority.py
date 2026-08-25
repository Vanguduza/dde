"""Chapter 13.9 tenancy authority (DDE-051): Organization above Tenant,
organization-scoped principal grants, composite scope-binding foreign keys.

Depends on 0019 (donor-taint chain).

What this migration adds on top of 0001..0019:

1. `organizations` -- top of the Ch.13.9 scope chain
   (Principal -> Organization/Tenant -> Project -> Mission -> Task ->
   runtime bindings), with the same fail-closed RLS shape as every
   tenant-scoped table, keyed on its own GUC `dde.organization_id`.
2. `tenants.organization_id NOT NULL` + FK to `organizations`.
3. `principal_grants.scope_type` / `.grant_scope` with CHECK constraints
   (Ch.14.2: authorization is RBAC plus contextual constraints; an
   ORGANIZATION grant covers every tenant of one organization).
4. Composite scope-binding FKs replacing single-column ones on artifacts /
   task_attempts / worker_runs / verification_runs so a row can never
   reference another scope's parent (a lone mission_id FK admits a
   cross-scope reference whose ids are all individually valid -- exactly
   the hole Ch.13.9's object-layer mediation closes at the database layer).
   Parent-side UNIQUE indexes back each composite reference.

Reversal drops what this created and restores the 0019-era shape.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

_ORG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS organizations (
    organization_id uuid NOT NULL,
    slug text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (organization_id),
    UNIQUE (slug)
);
"""

# asyncpg cannot run multi-command strings as one prepared statement, so
# each DDL statement below is executed separately.
_ORG_RLS_SQL = [
    "ALTER TABLE organizations ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE organizations FORCE ROW LEVEL SECURITY",
    "DROP POLICY IF EXISTS organizations_tenant_isolation ON organizations",
    """
CREATE POLICY organizations_tenant_isolation ON organizations
    USING (
        organization_id = CAST(current_setting('dde.organization_id', true) AS uuid)
    )
    WITH CHECK (
        organization_id = CAST(current_setting('dde.organization_id', true) AS uuid)
    )
""",
]

# Parent-side UNIQUE indexes backing the composite FKs below. The missions /
# tasks / task_attempts / worker_runs tables carry these column sets already
# but had no UNIQUE constraint over them; CREATE UNIQUE INDEX IF NOT EXISTS
# keeps the migration idempotent on an empty or populated database.
_PARENT_INDEXES = [
    ("uq_missions_scope", "missions", "mission_id, project_id, tenant_id"),
    ("uq_tasks_scope", "tasks", "task_id, project_id, tenant_id"),
    ("uq_task_attempts_scope", "task_attempts", "attempt_id, project_id, tenant_id"),
    ("uq_worker_runs_scope", "worker_runs", "run_id, project_id, tenant_id"),
]

_GRANTS_SQL = [
    """
ALTER TABLE principal_grants
    ADD COLUMN IF NOT EXISTS scope_type text NOT NULL DEFAULT 'PROJECT'
""",
    """
ALTER TABLE principal_grants
    ADD COLUMN IF NOT EXISTS grant_scope text NOT NULL DEFAULT 'PROJECT'
""",
    """
ALTER TABLE principal_grants DROP CONSTRAINT IF EXISTS
    principal_grants_scope_type_allowed
""",
    """
ALTER TABLE principal_grants ADD CONSTRAINT principal_grants_scope_type_allowed
    CHECK (scope_type IN ('ORGANIZATION', 'PROJECT'))
""",
    """
ALTER TABLE principal_grants DROP CONSTRAINT IF EXISTS
    principal_grants_grant_scope_allowed
""",
    """
ALTER TABLE principal_grants ADD CONSTRAINT principal_grants_grant_scope_allowed
    CHECK (grant_scope IN ('ORGANIZATION', 'TENANT', 'PROJECT'))
""",
]

# (table, old single-column FK, new composite FK, child columns,
#  parent table, parent columns)
_SCOPE_FKS = [
    (
        "artifacts",
        "artifacts_mission_id_fkey",
        "artifacts_mission_scope_fkey",
        "(mission_id, project_id, tenant_id)",
        "missions",
        "(mission_id, project_id, tenant_id)",
    ),
    (
        "task_attempts",
        "task_attempts_mission_id_fkey",
        "task_attempts_mission_scope_fkey",
        "(mission_id, project_id, tenant_id)",
        "missions",
        "(mission_id, project_id, tenant_id)",
    ),
    (
        "task_attempts",
        "task_attempts_task_id_fkey",
        "task_attempts_task_scope_fkey",
        "(task_id, project_id, tenant_id)",
        "tasks",
        "(task_id, project_id, tenant_id)",
    ),
    (
        "worker_runs",
        "worker_runs_task_attempt_id_fkey",
        "worker_runs_task_attempt_scope_fkey",
        "(task_attempt_id, project_id, tenant_id)",
        "task_attempts",
        "(attempt_id, project_id, tenant_id)",
    ),
    (
        "worker_runs",
        "worker_runs_mission_id_fkey",
        "worker_runs_mission_scope_fkey",
        "(mission_id, project_id, tenant_id)",
        "missions",
        "(mission_id, project_id, tenant_id)",
    ),
    (
        "verification_runs",
        "verification_runs_mission_id_fkey",
        "verification_runs_mission_scope_fkey",
        "(mission_id, project_id, tenant_id)",
        "missions",
        "(mission_id, project_id, tenant_id)",
    ),
    (
        "verification_runs",
        "verification_runs_task_id_fkey",
        "verification_runs_task_scope_fkey",
        "(task_id, project_id, tenant_id)",
        "tasks",
        "(task_id, project_id, tenant_id)",
    ),
    (
        "verification_runs",
        "verification_runs_task_attempt_id_fkey",
        "verification_runs_attempt_scope_fkey",
        "(task_attempt_id, project_id, tenant_id)",
        "task_attempts",
        "(attempt_id, project_id, tenant_id)",
    ),
    (
        "verification_runs",
        "verification_runs_worker_run_id_fkey",
        "verification_runs_worker_run_scope_fkey",
        "(worker_run_id, project_id, tenant_id)",
        "worker_runs",
        "(run_id, project_id, tenant_id)",
    ),
]

# Downgrade: new composite FK -> original single-column FK.
_DOWNGRADE_FKS = [
    (
        "artifacts",
        "artifacts_mission_scope_fkey",
        "artifacts_mission_id_fkey",
        "(mission_id) REFERENCES missions (mission_id)",
    ),
    (
        "task_attempts",
        "task_attempts_mission_scope_fkey",
        "task_attempts_mission_id_fkey",
        "(mission_id) REFERENCES missions (mission_id)",
    ),
    (
        "task_attempts",
        "task_attempts_task_scope_fkey",
        "task_attempts_task_id_fkey",
        "(task_id) REFERENCES tasks (task_id)",
    ),
    (
        "worker_runs",
        "worker_runs_task_attempt_scope_fkey",
        "worker_runs_task_attempt_id_fkey",
        "(task_attempt_id) REFERENCES task_attempts (attempt_id)",
    ),
    (
        "worker_runs",
        "worker_runs_mission_scope_fkey",
        "worker_runs_mission_id_fkey",
        "(mission_id) REFERENCES missions (mission_id)",
    ),
    (
        "verification_runs",
        "verification_runs_mission_scope_fkey",
        "verification_runs_mission_id_fkey",
        "(mission_id) REFERENCES missions (mission_id)",
    ),
    (
        "verification_runs",
        "verification_runs_task_scope_fkey",
        "verification_runs_task_id_fkey",
        "(task_id) REFERENCES tasks (task_id)",
    ),
    (
        "verification_runs",
        "verification_runs_attempt_scope_fkey",
        "verification_runs_task_attempt_id_fkey",
        "(task_attempt_id) REFERENCES task_attempts (attempt_id)",
    ),
    (
        "verification_runs",
        "verification_runs_worker_run_scope_fkey",
        "verification_runs_worker_run_id_fkey",
        "(worker_run_id) REFERENCES worker_runs (run_id)",
    ),
]


def _constraint_exists(conn: object, name: str, table: str) -> bool:
    row = conn.execute(  # type: ignore[attr-defined]
        text(
            "SELECT 1 FROM pg_constraint con JOIN pg_class rel "
            "ON rel.oid = con.conrelid JOIN pg_namespace nsp "
            "ON nsp.oid = rel.relnamespace WHERE con.conname = :name "
            "AND rel.relname = :table AND nsp.nspname = 'public'"
        ),
        {"name": name, "table": table},
    ).first()
    return row is not None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(_ORG_TABLE_SQL))
    for statement in _ORG_RLS_SQL:
        conn.execute(text(statement))

    # A placeholder org absorbs pre-existing tenant rows so the NOT NULL
    # link lands cleanly on an existing database; fresh databases get their
    # tenants created inside an organization through the seed/authority path.
    placeholder = conn.execute(  # type: ignore[attr-defined]
        text(
            "INSERT INTO organizations "
            "(organization_id, slug, created_at, updated_at) "
            "VALUES (gen_random_uuid(), 'system-root', now(), now()) "
            "ON CONFLICT (slug) DO UPDATE SET updated_at = organizations.updated_at "
            "RETURNING organization_id"
        )
    ).scalar_one()

    conn.execute(  # type: ignore[attr-defined]
        text("SELECT set_config('dde.organization_id', :value, true)"),
        {"value": str(placeholder)},
    )
    # Existing databases may predate the organization link entirely.
    conn.execute(  # type: ignore[attr-defined]
        text(
            "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS "
            "organization_id uuid REFERENCES organizations (organization_id)"
        )
    )
    # RLS on tenants binds tenant_id to dde.tenant_id; the dev superuser and
    # migrations run as owner/superuser so this link update is not blocked.
    conn.execute(  # type: ignore[attr-defined]
        text(
            "UPDATE tenants SET organization_id = :org "
            "WHERE organization_id IS NULL"
        ),
        {"org": placeholder},
    )
    conn.execute(  # type: ignore[attr-defined]
        text("ALTER TABLE tenants ALTER COLUMN organization_id SET NOT NULL")
    )
    if not _constraint_exists(conn, "tenants_organization_id_fkey", "tenants"):
        conn.execute(  # type: ignore[attr-defined]
            text(
                "ALTER TABLE tenants ADD CONSTRAINT tenants_organization_id_fkey "
                "FOREIGN KEY (organization_id) "
                "REFERENCES organizations (organization_id)"
            )
        )

    for index, table, columns in _PARENT_INDEXES:
        conn.execute(  # type: ignore[attr-defined]
            text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {index} ON {table} ({columns})"
            )
        )

    for statement in _GRANTS_SQL:
        conn.execute(text(statement))

    for table, old_name, new_name, cols, ref_table, ref_cols in _SCOPE_FKS:
        if _constraint_exists(conn, old_name, table):
            conn.execute(  # type: ignore[attr-defined]
                text(f"ALTER TABLE {table} DROP CONSTRAINT {old_name}")
            )
        if not _constraint_exists(conn, new_name, table):
            conn.execute(  # type: ignore[attr-defined]
                text(
                    f"ALTER TABLE {table} ADD CONSTRAINT {new_name} "
                    f"FOREIGN KEY {cols} REFERENCES {ref_table} {ref_cols}"
                )
            )


def downgrade() -> None:
    conn = op.get_bind()
    for table, new_name, old_name, definition in _DOWNGRADE_FKS:
        if _constraint_exists(conn, new_name, table):
            conn.execute(  # type: ignore[attr-defined]
                text(f"ALTER TABLE {table} DROP CONSTRAINT {new_name}")
            )
        if not _constraint_exists(conn, old_name, table):
            conn.execute(  # type: ignore[attr-defined]
                text(f"ALTER TABLE {table} ADD CONSTRAINT {old_name} FOREIGN KEY {definition}")
            )
    for index, _table, _columns in _PARENT_INDEXES:
        conn.execute(text(f"DROP INDEX IF EXISTS {index}"))  # type: ignore[arg-type]
    conn.execute(  # type: ignore[attr-defined]
        text(
            "ALTER TABLE principal_grants DROP CONSTRAINT IF EXISTS "
            "principal_grants_scope_type_allowed"
        )
    )
    conn.execute(  # type: ignore[attr-defined]
        text(
            "ALTER TABLE principal_grants DROP CONSTRAINT IF EXISTS "
            "principal_grants_grant_scope_allowed"
        )
    )
    conn.execute(  # type: ignore[attr-defined]
        text(
            "ALTER TABLE principal_grants "
            "DROP COLUMN IF EXISTS grant_scope, DROP COLUMN IF EXISTS scope_type"
        )
    )
    conn.execute(  # type: ignore[attr-defined]
        text(
            "ALTER TABLE tenants DROP CONSTRAINT IF EXISTS "
            "tenants_organization_id_fkey"
        )
    )
    conn.execute(  # type: ignore[attr-defined]
        text("ALTER TABLE tenants DROP COLUMN IF EXISTS organization_id")
    )
    conn.execute(text("DROP TABLE IF EXISTS organizations CASCADE"))  # type: ignore[arg-type]
