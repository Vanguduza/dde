"""Chapter 11.6 bidirectional migration verification.

Mechanism (documented per the mission's acceptance item 3):

- **forward_empty** — open a throwaway database via the *existing* engine
  connection (`CREATE DATABASE` on a fresh autocommit connection), then
  drive Alembic programmatically (`alembic.command.upgrade`) to `head`
  against that empty database. This proves the full chain applies from
  nothing.
- **forward_previous** — create a second throwaway database, replay the
  chain up to `previous_release_revision` (the previous release's schema),
  then upgrade only the remainder to `head`. This proves the new revisions
  apply *on top of* the previous release — the half Chapter 11.6 declares
  mandatory ("a migration that only works on an empty database is not
  verified").

Both halves run inside this process through `engine.truth.db.build_engine`
connections; no shell-out, no second alembic.ini, and the throwaway
databases are dropped in `dispose()` so the verification leaves nothing
behind.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import alembic.command
import alembic.config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


@dataclass(frozen=True)
class VerificationResult:
    head: str
    forward_empty_verified: bool = False
    forward_previous_verified: bool = False


def _make_url(base_url: str, database: str) -> str:
    """Swap the database name in the asyncpg URL for a throwaway one."""
    if "/" not in base_url:
        raise ValueError("database_url must contain a database segment")
    prefix, _, _ = base_url.rpartition("/")
    return f"{prefix}/{database}"


class MigrationVerifier:
    """Drives the two mandatory Chapter 11.6 verification halves."""

    def __init__(
        self,
        admin_engine: AsyncEngine,
        *,
        database_url: str,
        scratch_prefix: str,
    ) -> None:
        self._admin_engine = admin_engine
        self._database_url = database_url
        self._scratch_prefix = scratch_prefix
        self._created: list[str] = []

    @classmethod
    async def create(cls, engine: AsyncEngine) -> MigrationVerifier:
        """Build a verifier bound to the same server as ``engine``.

        The URL must keep its credential material: ``str(engine.url)``
        masks the password, and every scratch connection made from the
        masked string fails server authentication.
        """
        url = engine.url.render_as_string(hide_password=False)
        return cls(
            engine,
            database_url=url,
            scratch_prefix=f"dde_verify_{datetime.now(UTC).strftime('%H%M%S%f')}",
        )

    async def dispose(self) -> None:
        """Drop every throwaway database this verifier created."""
        for database in self._created:
            await self._drop_database(database)

    def _alembic_config(self) -> alembic.config.Config:
        config = alembic.config.Config("alembic.ini")
        config.set_main_option("script_location", "migrations")
        return config

    def _upgrade_on_connection(self, revision: str):  # type: ignore[no-untyped-def]
        """The run_sync body: run one alembic upgrade on the given
        connection. ``migrations/env.py`` consumes the connection through
        ``config.attributes['connection']`` instead of opening its own
        engine (and calling ``asyncio.run``, which is forbidden inside a
        live loop)."""

        def _body(connection) -> None:  # type: ignore[no-untyped-def]
            config = self._alembic_config()
            config.attributes["connection"] = connection
            alembic.command.upgrade(config, revision)

        return _body

    def _downgrade_on_connection(self, revision: str):  # type: ignore[no-untyped-def]
        """The run_sync body for one alembic downgrade -- the mirror of
        `_upgrade_on_connection`, same programmatic-connection path."""

        def _body(connection) -> None:  # type: ignore[no-untyped-def]
            config = self._alembic_config()
            config.attributes["connection"] = connection
            alembic.command.downgrade(config, revision)

        return _body

    async def _create_database(self, database: str) -> None:
        async with self._admin_engine.connect() as connection:
            autocommit = await connection.execution_options(
                isolation_level="AUTOCOMMIT"
            )
            await autocommit.execute(text(f'CREATE DATABASE "{database}"'))  # noqa: S608
        self._created.append(database)

    async def _drop_database(self, database: str) -> None:
        async with self._admin_engine.connect() as connection:
            autocommit = await connection.execution_options(
                isolation_level="AUTOCOMMIT"
            )
            await autocommit.execute(
                text(f'DROP DATABASE IF EXISTS "{database}"')  # noqa: S608
            )

    @staticmethod
    def _database_revision_sync(connection) -> str | None:  # type: ignore[no-untyped-def]
        """The revision THIS database is currently at (its alembic_version
        row) -- distinct from the script directory's head, which is a
        property of the codebase and always names the newest revision no
        matter where any given database stands."""
        from sqlalchemy import text as _text

        version = connection.execute(
            _text("SELECT version_num FROM alembic_version")
        ).scalar()
        return str(version) if version is not None else None

    async def verify_forward_empty(
        self, *, head: str, previous_release_revision: str
    ) -> VerificationResult:
        """Half one: the whole chain applies to an empty database."""
        del previous_release_revision
        database = f"{self._scratch_prefix}_empty"
        await self._create_database(database)

        scratch_engine = create_async_engine(_make_url(self._database_url, database))
        try:
            async with scratch_engine.connect() as connection:
                await connection.run_sync(self._upgrade_on_connection(head))
                landed = await connection.run_sync(self._database_revision_sync)
        finally:
            await scratch_engine.dispose()
        if landed != head:
            raise RuntimeError(f"forward-empty landed at {landed}, expected {head}")
        return VerificationResult(head=head, forward_empty_verified=True)

    async def verify_downgrade_reversible(
        self, *, head: str, baseline: str
    ) -> VerificationResult:
        """Reversibility half (AGENTS.md definition of done: every
        migration applies cleanly to an empty database AND is
        reversible). Forward-applies to ``head`` on a throwaway
        database, downgrades back to ``baseline``, and proves the
        database actually stands on ``baseline`` afterwards -- the same
        programmatic connection path as the forward halves."""
        if baseline == head:
            raise ValueError("baseline must differ from head")
        database = f"{self._scratch_prefix}_down"
        await self._create_database(database)

        scratch_engine = create_async_engine(_make_url(self._database_url, database))
        try:
            async with scratch_engine.connect() as connection:
                await connection.run_sync(self._upgrade_on_connection(head))
                await connection.run_sync(self._downgrade_on_connection(baseline))
                landed = await connection.run_sync(self._database_revision_sync)
        finally:
            await scratch_engine.dispose()
        if landed != baseline:
            raise RuntimeError(f"downgrade landed at {landed}, expected {baseline}")
        return VerificationResult(head=head, forward_empty_verified=True)

    async def verify_forward_previous(
        self, *, previous_release_revision: str
    ) -> VerificationResult:
        """Half two: post-baseline revisions apply to a snapshot of the
        previous release's schema."""
        database = f"{self._scratch_prefix}_prev"
        await self._create_database(database)

        scratch_engine = create_async_engine(_make_url(self._database_url, database))
        try:
            async with scratch_engine.connect() as connection:
                await connection.run_sync(
                    self._upgrade_on_connection(previous_release_revision)
                )
                current_head = await connection.run_sync(self._database_revision_sync)
                if current_head != previous_release_revision:
                    raise RuntimeError(
                        "baseline snapshot landed at "
                        f"{current_head}, expected {previous_release_revision}"
                    )
                await connection.run_sync(self._upgrade_on_connection("head"))
                final_head = await connection.run_sync(self._database_revision_sync)
                if final_head is None:
                    raise RuntimeError(
                        "forward-previous finished with no alembic_version row"
                    )
        finally:
            await scratch_engine.dispose()
        return VerificationResult(head=final_head, forward_previous_verified=True)
