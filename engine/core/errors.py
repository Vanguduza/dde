"""Typed error mapping to the Chapter 15.5 contract.

Chapter 15.4's error taxonomy is a closed vocabulary of `error_code` strings
(`DdeError` is the boundary mapping; the recovery matrix aliases adapter
codes onto it). A new code enters only when a real production mutation site
needs to distinguish a condition every existing code would misreport. For
caller-supplied budget ceilings no new string was needed:
`engine.recovery.matrix.FAILURE_CLASS_ALIASES` already maps
`BUDGET_EXCEEDED` onto `RESOURCE_EXHAUSTION`, but nothing in `engine/**`
ever raised it -- so a ceiling being hit was indistinguishable from the
check not existing at all. `BudgetExhaustedError` gives that existing code
a raiser plus a catchable type.
"""

from __future__ import annotations

from engine.contracts.error import Error
from engine.core.ids import uuid7


class DdeError(Exception):
    """Domain error that maps onto the gateway Error contract."""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, object] | None = None,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.retryable = retryable
        self.details = details
        self.correlation_id = correlation_id or str(uuid7())

    def to_contract(self) -> Error:
        return Error(
            error_code=self.error_code,
            message=self.message,
            retryable=self.retryable,
            details=self.details,
            correlation_id=self.correlation_id,
        )


class BudgetExhaustedError(DdeError):
    """A caller-supplied budget ceiling for one dispatch attempt was hit
    before the attempt could run. Fixed code `BUDGET_EXCEEDED` -- the
    recovery matrix's existing alias for RESOURCE_EXHAUSTION
    (`engine.recovery.matrix.FAILURE_CLASS_ALIASES`) -- rather than a new
    near-duplicate string; non-retryable per Chapter 15.4; carries both the
    ceiling and the observed demand in `details`. Subclassing rather than
    raising bare `DdeError` lets a caller distinguish "stop, the budget
    said no" from any other refusal-shaped error without string-matching
    messages. It deliberately does NOT auto-pause anything: pausing-for-
    human is the recovery matrix's RESOURCE_EXHAUSTION row
    (`action="request_budget"`, `requires_human=True`), which a dispatcher
    reaches by recording this failure class on the run/attempt -- that
    consumer remains deferred; see `engine.workers.service`."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            "BUDGET_EXCEEDED",
            message,
            retryable=False,
            details=details,
        )
