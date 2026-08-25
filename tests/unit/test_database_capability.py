"""DDE-049 capability.database / db_assertion proofs.

Chapter 11.2's `db_assertion` binding ("still needs DDE-049" per
`engine.verification.oracle`) and Chapter 9.8's backend/database class.
The executor is an in-process read-only SQL assertion runner over the
product datastore URL; DDL/DML in an assertion file is refused — the
capability is PURE_READ by construction, not by promise.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from engine.capabilities.database import (
    DatabaseAssertionResult,
    DatabaseAssertionSpec,
)
from engine.capabilities.database.assertions import InProcessDatabaseAsserter
from engine.capabilities.seed import SEED_CAPABILITIES
from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.routing.policy import CAPABILITY_DATABASE, PROFILE_DATABASE
from engine.routing.registry import PROFILES
from engine.verification.checks import CheckSpec, run_check
from engine.verification.oracle import validate_definition
from tests.support.db import get_settings


async def _product_database_url() -> str:
    """The shared test PostgreSQL URL (the DDE control-plane database)."""
    return get_settings().database_url


def test_capability_database_is_in_seed_portfolio() -> None:
    ids = {spec.capability_id for spec in SEED_CAPABILITIES}
    assert CAPABILITY_DATABASE in ids
    database = next(
        s for s in SEED_CAPABILITIES if s.capability_id == CAPABILITY_DATABASE
    )
    assert database.side_effect_class == "PURE_READ"
    assert database.enforcement_tier == "T1"


def test_database_profile_declares_capability() -> None:
    assert PROFILE_DATABASE in PROFILES
    assert CAPABILITY_DATABASE in PROFILES[PROFILE_DATABASE].capabilities


def test_db_assertion_is_a_valid_oracle_binding() -> None:
    validate_definition(
        scope="task",
        observable_outcomes=[
            CheckSpec(
                outcome_id=uuid7(),
                statement="seeded table holds exactly two rows",
                kind="db_assertion",
                ref="sql/assertions/seed_rows.sql",
                command=["SELECT count(*) = 2 FROM dde049_items"],
            )
        ],
        negative_cases=[],
        minimum_confidence=1.0,
    )


@pytest.mark.asyncio
async def test_asserter_runs_true_statement(tmp_path: Path) -> None:
    url = await _product_database_url()
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE IF NOT EXISTS dde049_items (id int)"))
            await conn.execute(text("TRUNCATE dde049_items"))
            await conn.execute(
                text("INSERT INTO dde049_items VALUES (1), (2)")  # noqa: S608
            )
    finally:
        await engine.dispose()
    result = await InProcessDatabaseAsserter().assert_(
        DatabaseAssertionSpec(
            datastore_url=url,
            statements=("SELECT count(*) = 2 FROM dde049_items",),
        )
    )
    assert result.passed is True
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
    assert payload["results"][0]["passed"] is True


@pytest.mark.asyncio
async def test_asserter_fails_false_statement(tmp_path: Path) -> None:
    url = await _product_database_url()
    result = await InProcessDatabaseAsserter().assert_(
        DatabaseAssertionSpec(
            datastore_url=url,
            statements=("SELECT 1 = 2",),
        )
    )
    assert result.passed is False
    payload = json.loads(result.stdout)
    assert payload["results"][0]["passed"] is False


@pytest.mark.asyncio
async def test_asserter_refuses_mutating_statements(tmp_path: Path) -> None:
    url = await _product_database_url()
    asserter = InProcessDatabaseAsserter()
    for sql in (
        "DROP TABLE anything",
        "DELETE FROM x",
        "INSERT INTO x VALUES (1)",
        "UPDATE x SET a = 1",
        "ALTER TABLE x ADD COLUMN b int",
        "CREATE TABLE y (id int)",
        "GRANT ALL ON x TO public",
    ):
        with pytest.raises(DdeError) as exc:
            await asserter.assert_(
                DatabaseAssertionSpec(datastore_url=url, statements=(sql,))
            )
        assert exc.value.error_code == "POLICY_DENIED"


@pytest.mark.asyncio
async def test_asserter_refuses_multiple_statements_per_query(tmp_path: Path) -> None:
    url = await _product_database_url()
    with pytest.raises(DdeError) as exc:
        await InProcessDatabaseAsserter().assert_(
            DatabaseAssertionSpec(
                datastore_url=url,
                statements=("SELECT true; DROP TABLE x",),
            )
        )
    assert exc.value.error_code == "VALIDATION_FAILED"


def _workspace(tmp_path: Path) -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        workspace_id=uuid7(),
        tenant_id=uuid7(),
        project_id=uuid7(),
        mission_id=uuid7(),
        task_id=uuid7(),
        execution_environment_id=uuid7(),
        base_revision="HEAD",
        current_revision="HEAD",
        workspace_path=str(tmp_path),
        policy={},
        status="READY",
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_db_assertion_check_uses_injected_asserter(tmp_path: Path) -> None:
    url = await _product_database_url()

    class _AlwaysPass:
        async def assert_(self, spec: DatabaseAssertionSpec):
            del spec
            return DatabaseAssertionResult(
                exit_code=0,
                stdout='{"passed":true}',
                stderr="",
                duration_ms=1,
                timed_out=False,
                passed=True,
            )

    result = await run_check(
        workspaces=None,  # type: ignore[arg-type]
        workspace=_workspace(tmp_path),
        spec=CheckSpec(
            outcome_id=uuid7(),
            statement="rows exist",
            kind="db_assertion",
            ref="sql/assertions/x.sql",
            command=[url, "SELECT count(*) > 0 FROM dde049_items"],
        ),
        database=_AlwaysPass(),  # type: ignore[arg-type]
    )
    assert result.status == "PASSED"
