"""Process clock for durable timestamps."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return a timezone-aware timestamp."""


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
