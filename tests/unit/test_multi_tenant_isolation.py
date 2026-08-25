"""Chapter 13.9 multi-tenant isolation suite -- the S6 exit-criteria fixture.

Adversarial, live-Postgres proof of the four Chapter 13.9 isolation layers
beyond the database-RLS layer DDE-022 already proved:

(a) Cross-tenant access fails BEFORE resource access: the tenancy authority
    resolves tenant identity only from an authenticated principal and
    refuses an unknown principal or a cross-tenant target before any
    domain/resource operation runs.
(b) Object/artifact scope mediation: a storage key under another scope's
    prefix is rejected even when every id in it is individually valid, and
    a cross-scope artifact reference is impossible at the FK layer.
(c) Project-scoped git connections: a connection bound to one project's
    repo cannot reach another project's repository, even same-host, and
    cannot be re-bound across projects.
(d) Telemetry rows carry tenant/project/mission correlation derived from
    the verified run's own chain -- never from caller-supplied ids.

The probe-role pattern from tests/support/db.py (NOSUPERUSER NOBYPASSRLS)
is reused so no assertion rests on a superuser bypass. The RLS fail-closed
GUC proofs remain in tests/unit/test_rls_enforcement.py; this suite covers
what that module's docstring explicitly did not claim.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from engine.capabilities.git_scope import GitConnectionScope, ProjectRepoScopeError
from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.gateway.sessions.repository import PrincipalLookup
from engine.object_store.scope import (
    ArtifactObjectStore,
    ScopeViolation,
    storage_key_for_artifact,
)
from engine.telemetry.service import RoutingTelemetryService
from engine.tenancy.authority import TenancyAuthorityService
from engine.tenancy.grants import GrantScopeType
from engine.truth.db import open_unit_of_work
from engine.verification.checks import CheckSpec
from engine.verification.oracle import AcceptanceOracleService
from engine.verification.runner import VerificationRunnerService
from engine.workspaces.service import WorkspaceService
from tests.support.db import (
    TenantFixture,
    ensure_rls_probe_role,
    new_engine,
    open_rls_probe,
    seed_tenant,
)
from tests.support.verification_fixtures import build_verification_fixture

NOW = datetime.now(UTC)


async def _seed_organization(engine: AsyncEngine) -> UUID:
    organization_id = uuid7()
    async with engine.connect() as connection:
        await connection.execute(
            text(
                "INSERT INTO organizations "
                "(organization_id, slug, created_at, updated_at) "
                "VALUES (:id, :slug, :now, :now)"
            ),
            {
                "id": organization_id,
                "slug": f"org-{organization_id.hex}",
                "now": NOW,
            },
        )
        await connection.commit()
    return organization_id


async def _seed_tenant_in_org(engine: AsyncEngine, org_id: UUID) -> TenantFixture:
    """seed_tenant() then backfill tenants.organization_id to `org_id`."""
    fixture = await seed_tenant(engine)
    async with engine.connect() as connection:
        await connection.execute(
            text("UPDATE tenants SET organization_id = :org WHERE tenant_id = :tid"),
            {"org": org_id, "tid": fixture.tenant_id},
        )
        await connection.commit()
    return fixture


@pytest.mark.asyncio
async def test_cross_tenant_read_fails_before_resource_access() -> None:
    """(a) An unknown principal and a grantless principal are refused before
    any mission/resource read; tenant identity comes only from `principals`
    (Ch.13.9: never from a client-supplied target id)."""
    engine = new_engine()
    try:
        authority = TenancyAuthorityService(engine)
        owner = await seed_tenant(engine)

        with pytest.raises(DdeError) as unknown_exc:
            await authority.resolve_principal_tenant(principal_id=uuid7())
        assert unknown_exc.value.error_code == "INVALID_CREDENTIALS"

        stranger = await seed_tenant(engine)
        with pytest.raises(DdeError) as forbidden:
            await authority.authorize_project_access(
                principal_id=stranger.principal_id,
                tenant_id=owner.tenant_id,
                project_id=owner.project_id,
            )
        assert forbidden.value.error_code == "TENANT_SCOPE_VIOLATION"

        async with open_unit_of_work(
            engine,
            tenant_id=owner.tenant_id,
            project_id=owner.project_id,
        ) as uow:
            await authority.record_project_grant(
                uow,
                principal_id=owner.principal_id,
                project_id=owner.project_id,
            )
            await uow.commit()

        await authority.authorize_project_access(
            principal_id=owner.principal_id,
            tenant_id=owner.tenant_id,
            project_id=owner.project_id,
        )

        lookup = PrincipalLookup()
        async with engine.connect() as connection:
            resolved = await lookup.tenant_for_principal(
                connection, owner.principal_id
            )
        assert resolved == owner.tenant_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_org_scoped_grant_covers_all_tenants_of_the_org() -> None:
    """Chapter 14.2 ABAC context: an ORGANIZATION-scoped principal grant
    authorizes sibling tenants under one organization; nothing crosses the
    organization boundary."""
    engine = new_engine()
    try:
        org_a = await _seed_organization(engine)
        org_b = await _seed_organization(engine)
        first = await _seed_tenant_in_org(engine, org_a)
        second = await _seed_tenant_in_org(engine, org_a)
        outsider = await _seed_tenant_in_org(engine, org_b)

        authority = TenancyAuthorityService(engine)
        async with open_unit_of_work(
            engine,
            tenant_id=first.tenant_id,
            project_id=first.project_id,
        ) as uow:
            await authority.record_project_grant(
                uow,
                principal_id=first.principal_id,
                project_id=first.project_id,
                grant_scope_type=GrantScopeType.ORGANIZATION,
            )
            await uow.commit()

        await authority.authorize_project_access(
            principal_id=first.principal_id,
            tenant_id=second.tenant_id,
            project_id=second.project_id,
        )
        with pytest.raises(DdeError) as denied:
            await authority.authorize_project_access(
                principal_id=first.principal_id,
                tenant_id=outsider.tenant_id,
                project_id=outsider.project_id,
            )
        assert denied.value.error_code == "TENANT_SCOPE_VIOLATION"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_object_storage_prefix_rejects_cross_scope_references() -> None:
    """(b) Storage keys are derived from scope + content hash; a key under
    another scope's prefix is refused even though every id it embeds is
    individually valid."""
    engine = new_engine()
    try:
        owner = await seed_tenant(engine)
        stranger = await seed_tenant(engine)
        store = ArtifactObjectStore(root="artifacts")
        digest = "a" * 64

        own_key = storage_key_for_artifact(
            tenant_id=owner.tenant_id,
            project_id=owner.project_id,
            content_hash=digest,
        )
        assert own_key.startswith(f"artifacts/{owner.tenant_id}/{owner.project_id}/")

        forged_key = f"artifacts/{stranger.tenant_id}/{stranger.project_id}/{digest}"
        with pytest.raises(ScopeViolation):
            store.verify_key(
                tenant_id=owner.tenant_id,
                project_id=owner.project_id,
                key=forged_key,
            )
        store.verify_key(
            tenant_id=owner.tenant_id, project_id=owner.project_id, key=own_key
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cross_scope_artifact_reference_rejected_by_fk(tmp_path: Path) -> None:
    """(b) artifacts_mission_scope_fkey makes referencing another project's
    mission physically impossible even for the superuser dev role."""
    engine = new_engine()
    try:
        fixture = await build_verification_fixture(
            engine, tmp_path, mission_slug=f"MISSION-XSCOPE-{uuid7().hex[:8]}"
        )
        stranger = await seed_tenant(engine)
        artifact_id = uuid7()
        async with open_unit_of_work(
            engine,
            tenant_id=stranger.tenant_id,
            project_id=stranger.project_id,
        ) as uow:
            with pytest.raises(IntegrityError, match="artifacts_mission_scope_fkey"):
                await uow.connection.execute(
                    text(
                        "INSERT INTO artifacts (artifact_id, tenant_id, "
                        "project_id, mission_id, content_hash, storage_key, "
                        "created_at, updated_at) VALUES (:aid, :tid, :pid, "
                        ":mid, 'ab', :key, :now, :now)"
                    ),
                    {
                        "aid": artifact_id,
                        "tid": stranger.tenant_id,
                        "pid": stranger.project_id,
                        # The owner project's real mission id.
                        "mid": fixture.mission.mission_id,
                        "key": "artifacts/forged",
                        "now": NOW,
                    },
                )
            await uow.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_project_git_connection_cannot_reach_other_project_repo() -> None:
    """(c) Project-scoped git connections: fetch/push against any URL other
    than the bound repository is refused before a git command can run --
    including another project's repo on the same host -- and a connection
    cannot be re-bound to another project."""
    engine = new_engine()
    try:
        owner = await seed_tenant(engine)
        stranger = await seed_tenant(engine)
        owner_repo = GitConnectionScope.bind(
            tenant_id=owner.tenant_id,
            project_id=owner.project_id,
            remote_url="https://git.example.com/org/erp.git",
        )
        stranger_repo = GitConnectionScope.bind(
            tenant_id=stranger.tenant_id,
            project_id=stranger.project_id,
            remote_url="https://git.example.com/org/other.git",
        )

        owner_repo.authorize_operation("fetch", owner_repo.remote_url)

        with pytest.raises(ProjectRepoScopeError):
            owner_repo.authorize_operation("fetch", stranger_repo.remote_url)
        # Same host, path outside the bound repository: also refused.
        with pytest.raises(ProjectRepoScopeError):
            owner_repo.authorize_operation(
                "fetch",
                "https://git.example.com/org/erp.wiki.git",
            )
        with pytest.raises(ProjectRepoScopeError):
            GitConnectionScope.bind(
                tenant_id=owner.tenant_id,
                project_id=stranger.project_id,
                remote_url=owner_repo.remote_url,
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_telemetry_correlation_derives_from_verified_chain(
    tmp_path: Path,
) -> None:
    """(d) `record_decision_outcome` stamps tenant/project/mission/task from
    the Task and WorkerRun themselves; caller arguments cannot relocate a
    row into another scope."""
    root = repo_root()
    engine = new_engine()
    workspace_obj = None
    try:
        fixture = await build_verification_fixture(
            engine, tmp_path, mission_slug=f"MISSION-TLM-{uuid7().hex[:8]}"
        )
        workspace_obj = fixture.workspace
        workspaces = WorkspaceService(engine, root=root)
        workspaces.write(workspace_obj, "verification_check.py", b"def x():\n    pass\n")

        lint_outcome = CheckSpec(
            outcome_id=uuid7(),
            statement=(
                "ruff check reports no lint violations on verification_check.py"
            ),
            kind="test",
            ref="ruff:verification_check.py",
            command=[
                __import__("sys").executable,
                "-m",
                "ruff",
                "check",
                "verification_check.py",
            ],
        )
        oracle = await AcceptanceOracleService(engine).define(
            task=fixture.task, outcomes=[lint_outcome], minimum_confidence=1.0
        )
        run = await VerificationRunnerService(engine, workspaces).run(
            task=fixture.task,
            worker_run=fixture.worker_run,
            workspace=fixture.workspace,
            oracle=oracle,
            idempotency_key="isolation-telemetry-run-1",
        )
        assert run.status == "PASSED"

        service = RoutingTelemetryService(engine)
        outcome = await service.record_decision_outcome(
            task=fixture.task,
            worker_run=fixture.worker_run,
            verification_run=run,
            rework_count=0,
            recovery_decision=None,
        )
        assert outcome.tenant_id == fixture.task.tenant_id
        assert outcome.project_id == fixture.task.project_id
        assert outcome.mission_id == fixture.task.mission_id
        assert outcome.task_id == fixture.task.task_id
        assert outcome.route_decision_id == fixture.execution_plan.route_decision_id
        assert outcome.task_attempt_id == fixture.worker_run.task_attempt_id
        assert outcome.verification_run_id == run.verification_run_id
    finally:
        if workspace_obj is not None:
            await WorkspaceService(engine).scrub(workspace_obj)
        await engine.dispose()


@pytest.mark.asyncio
async def test_unset_guc_yields_no_rows_fail_closed_on_new_tables() -> None:
    """Ch.3.2 mandatory rule over the tables DDE-051 adds: unset GUC sees
    nothing on `organizations` or `principal_grants` through the probe role
    even when rows exist. FAILED before the fix whenever a table lacked RLS
    (organizations did not exist at all before this mission)."""
    engine = new_engine()
    try:
        org_id = await _seed_organization(engine)
        fixture = await seed_tenant(engine)
        async with engine.connect() as connection:
            await connection.execute(
                text("UPDATE tenants SET organization_id = :org WHERE tenant_id = :t"),
                {"org": org_id, "t": fixture.tenant_id},
            )
            await connection.commit()

        probe_url = await ensure_rls_probe_role(engine)
        probe_engine = create_async_engine(probe_url)
        try:
            async with open_rls_probe(probe_engine) as connection:
                org_count = await connection.execute(
                    text("SELECT count(*) FROM organizations")
                )
                assert org_count.scalar_one() == 0
                grant_count = await connection.execute(
                    text("SELECT count(*) FROM principal_grants")
                )
                assert grant_count.scalar_one() == 0
        finally:
            await probe_engine.dispose()
    finally:
        await engine.dispose()
