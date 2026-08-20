"""Return types for Chapter 12.4 reconciliation -- split from
`engine.recovery.service` so production resolvers can import them without
a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.contracts.external_effect import ExternalEffect


@dataclass(frozen=True)
class ReconciliationOutcome:
    """A provider-specific resolver's real answer to "did the external
    mutation actually happen?". `verified=False` means the resolver could
    not determine either answer with confidence -- the only condition
    under which `reconcile()` raises rather than resolving. `present` is
    meaningful only when `verified=True`."""

    verified: bool
    present: bool
    detail: str


@dataclass(frozen=True)
class ReconciliationResult:
    """`reconcile()`'s return value. `verified_absent` is the Chapter
    12.4-governing fact a caller needs: `True` only when reconciliation
    positively confirmed the mutation never happened, the one condition
    under which a NEW mutation attempt is permitted."""

    effect: ExternalEffect
    verified_absent: bool
