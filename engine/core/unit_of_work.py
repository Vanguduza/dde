"""Unit of work spanning one PostgreSQL transaction (Chapter 3.5)."""

from __future__ import annotations

from typing import Protocol


class UnitOfWork(Protocol):
    """Modules share one transaction; they must not open independent ones."""

    async def commit(self) -> None:
        """Persist the unit of work."""

    async def rollback(self) -> None:
        """Discard the unit of work."""


class MemoryUnitOfWork:
    """In-process unit of work for contract and unit tests."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True
