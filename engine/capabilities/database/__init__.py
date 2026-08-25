"""Chapter 9 backend/database capability contract (DDE-049).

`db_assertion` execution is an in-process, read-only SQL assertion runner
(Chapter 11.2's `db_assertion` binding; `engine.verification.oracle`
flagged it "still needs DDE-049"). The protocol grants no write authority:
assertion statements are validated read-only before execution, so the
capability is PURE_READ by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DatabaseAssertionSpec:
    """One db_assertion check over a product datastore.

    `datastore_url` is an asyncpg URL for the datastore under test — a
    ProductEnvironment's `datastore_ref` resolved by the caller, never
    DDE's own control-plane credentials implied. Each statement must be a
    single read-only SELECT returning one boolean row.
    """

    datastore_url: str
    statements: tuple[str, ...]


@dataclass(frozen=True)
class DatabaseAssertionResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    passed: bool


class DatabaseCapability(Protocol):
    """T1-brokered database assertion. Callers must hold an active
    `capability.database` lease before invoking `assert_` — this protocol
    grants no write authority."""

    async def assert_(self, spec: DatabaseAssertionSpec) -> DatabaseAssertionResult: ...
